"""Opt-in, accountable discovery from already approved read-only award sources.

Administrator continuing authority is not academic approval or a legal basis.
Existing profile/source/issuer policy and immutable award receipts remain required.
"""
import hashlib
from datetime import timedelta
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.authorization import require_admin_permission
from apps.accounts.models import SecurityAudit, User
from config.spreadsheet_sources import validate_target
from .classroom_automation import require_postgres
from .importers.preview import ImportProblem, check_profile, confirm_preview, create_preview
from .importers.mapping import digest
from .importers.sheet_source import SheetUnavailable, read_profile_sheet
from .models import SpreadsheetAutomation, SpreadsheetPoll, SpreadsheetProfile, SpreadsheetPreview

PERMISSION = 'accounts.import_completions'
LEASE = timedelta(minutes=5)
STATES = ('IDLE', 'PROCESSING', 'COMPLETED', 'UNCHANGED', 'EXCLUDED', 'FAILED', 'DISABLED')


def current_actor(actor_id, *, lock=False):
    users = User.objects.select_for_update() if lock else User.objects
    actor = users.filter(pk=actor_id).first()
    # A fresh instance is deliberate: Django caches permission sets on User instances.
    require_admin_permission(actor, PERMISSION)
    return actor


def approved_policy(profile):
    if profile.source != 'BTU_GOOGLE_SHEETS' or profile.kind != 'SKILL_AWARD' or not profile.approval_reference.strip():
        raise ImportProblem('AUTOMATION_APPROVED_AWARD_PROFILE_REQUIRED', 400)
    check_profile(profile)
    from django.conf import settings
    sources = getattr(settings, 'BTU_SPREADSHEET_GOOGLE_SOURCES', {})
    target = sources.get(profile.definition.get('google_source')) if isinstance(sources, dict) else None
    try:
        area = validate_target(target)
        if target['worksheet'] != profile.definition.get('worksheet', 'Completions'):
            raise ValueError
    except (TypeError, ValueError):
        raise ImportProblem('GOOGLE_SOURCE_UNAVAILABLE', 503) from None
    return digest({'spreadsheet_id': target['spreadsheet_id'], 'worksheet': target['worksheet'],
                   'range': area, 'profile_sha256': profile.definition_sha256})


def configure_automation(profile_id, *, actor, enabled, interval_seconds=300, authorization_reference=''):
    current_actor(actor.pk)
    if type(enabled) is not bool:
        raise ImportProblem('INVALID_AUTOMATION_CONTROL', 400)
    if enabled and (type(interval_seconds) is not int or not 60 <= interval_seconds <= 86400
                    or not isinstance(authorization_reference, str) or not authorization_reference.strip()
                    or len(authorization_reference) > 255 or any(ord(c) < 32 for c in authorization_reference)):
        raise ImportProblem('INVALID_AUTOMATION_CONTROL', 400)
    profile = SpreadsheetProfile.objects.get(pk=profile_id)
    if enabled:
        approved_policy(profile)
    now = timezone.now()
    binding, _ = SpreadsheetAutomation.objects.get_or_create(profile=profile, defaults={
        'actor': actor, 'authorization_reference': authorization_reference.strip(), 'approved_at': now, 'next_poll_at': now})
    # All issuance guards lock this same binding before profile/student locks.
    with transaction.atomic():
        binding = SpreadsheetAutomation.objects.select_for_update().get(pk=binding.pk)
        fresh = current_actor(actor.pk, lock=True)
        profile = SpreadsheetProfile.objects.select_for_update().get(pk=profile_id)
        if enabled:
            binding.approved_target_sha256 = approved_policy(profile)
            binding.actor, binding.authorization_reference = fresh, authorization_reference.strip()
            binding.interval_seconds, binding.approved_at = interval_seconds, now
            # Re-enabling establishes fresh authority and revalidates the current snapshot.
            binding.source_sha256 = ''
        binding.enabled = enabled
        binding.next_poll_at = now
        binding.lease_token, binding.lease_until = None, None
        binding.last_state, binding.last_error_code = ('IDLE' if enabled else 'DISABLED'), ''
        binding.save()
    return binding


def require_automation_lease(binding_id, token, profile_id, actor_id):
    """Call inside the same transaction as each award; serialize administrator disable."""
    if not connection.in_atomic_block:
        raise ImportProblem('AUTOMATION_REQUIRES_TRANSACTION', 503)
    binding = SpreadsheetAutomation.objects.select_for_update().get(pk=binding_id)
    if (not binding.enabled or binding.lease_token != token or not binding.lease_until
            or binding.lease_until <= timezone.now() or binding.profile_id != profile_id or binding.actor_id != actor_id):
        raise ImportProblem('AUTOMATION_DISABLED_OR_LEASE_LOST')
    try:
        actor = current_actor(binding.actor_id, lock=True)
    except PermissionDenied:
        raise ImportProblem('AUTOMATION_ACTOR_UNAUTHORIZED', 403) from None
    profile = SpreadsheetProfile.objects.select_for_update().get(pk=profile_id)
    if approved_policy(profile) != binding.approved_target_sha256:
        raise ImportProblem('AUTOMATION_SOURCE_CHANGED_REAUTHORIZE')
    binding.lease_until = timezone.now() + LEASE
    binding.save(update_fields=['lease_until', 'updated_at'])
    return actor


@transaction.atomic
def claim_source():
    require_postgres()
    now = timezone.now()
    binding = SpreadsheetAutomation.objects.select_for_update(skip_locked=True).filter(
        enabled=True, next_poll_at__lte=now).filter(Q(lease_until__isnull=True) | Q(lease_until__lte=now)).order_by('next_poll_at', 'pk').first()
    if binding is None:
        return None
    # Make interrupted work visible rather than leaving it indefinitely PROCESSING.
    stale = binding.polls.filter(state='PROCESSING')
    SecurityAudit.objects.filter(pk__in=stale.values('audit_id')).update(status_code=503)
    stale.update(state='FAILED', error_code='AUTOMATION_LEASE_EXPIRED', finished_at=now)
    token = uuid4()
    binding.lease_token, binding.lease_until = token, now + LEASE
    binding.next_poll_at = now + timedelta(seconds=binding.interval_seconds)
    binding.last_state = 'PROCESSING'
    binding.save()
    audit = SecurityAudit.objects.create(actor_id=binding.actor_id, action='SpreadsheetAutomaticPoll',
        ip_digest=hashlib.sha256(b'integration-owned-local-worker').hexdigest())
    poll = SpreadsheetPoll.objects.create(automation=binding, actor_id=binding.actor_id, audit=audit, lease_token=token)
    return binding, poll


def _finish(binding, poll, *, state, error='', source_hash='', preview=None, counts=None, checkpoint=False):
    with transaction.atomic():
        # Use the same binding -> poll order as claim_source, including stale recovery.
        current = SpreadsheetAutomation.objects.select_for_update().get(pk=binding.pk)
        poll = SpreadsheetPoll.objects.select_for_update().get(pk=poll.pk)
        if poll.state != 'PROCESSING':
            return 'FAILED'
        if current.lease_token != poll.lease_token or not current.lease_until or current.lease_until <= timezone.now():
            state, error, checkpoint = 'FAILED', 'AUTOMATION_DISABLED_OR_LEASE_LOST', False
        poll.state, poll.error_code = state, error
        poll.source_sha256, poll.preview = source_hash, preview
        poll.counts, poll.finished_at = counts or {}, timezone.now()
        poll.save()
        SecurityAudit.objects.filter(pk=poll.audit_id).update(status_code=200 if state != 'FAILED' else 503)
        # A disabled/re-enabled source has a new token; a stale worker cannot restore it.
        if current.lease_token == poll.lease_token:
            current.last_state, current.last_error_code = state, error
            current.last_checked_at = poll.finished_at
            current.next_poll_at = poll.finished_at + timedelta(seconds=current.interval_seconds)
            current.lease_token, current.lease_until = None, None
            if checkpoint:
                current.source_sha256 = source_hash
            current.save()
    return state


def process_source(binding, poll):
    preview, source_hash, counts = None, '', {}
    try:
        with transaction.atomic():
            actor = require_automation_lease(binding.pk, poll.lease_token, binding.profile_id, binding.actor_id)
        profile = SpreadsheetProfile.objects.get(pk=binding.profile_id)
        rows, source_hash = read_profile_sheet(profile)
        with transaction.atomic():
            require_automation_lease(binding.pk, poll.lease_token, binding.profile_id, binding.actor_id)
        if source_hash == binding.source_sha256:
            return _finish(binding, poll, state='UNCHANGED', source_hash=source_hash, checkpoint=True)
        # Recover the same unexpired failed snapshot/attempt budget where possible.
        preview = SpreadsheetPreview.objects.filter(profile=profile, actor=actor, source_sha256=source_hash,
            state='FAILED', expires_at__gt=timezone.now(), attempts__lt=5).order_by('-created_at').first()
        preview = preview or create_preview(profile, rows, source_hash, actor=actor)
        counts = {key: preview.report[key] for key in ('total_rows', 'valid_records', 'duplicate_records', 'invalid_records', 'review_records')}
        if not preview.report['valid_records']:
            return _finish(binding, poll, state='EXCLUDED', source_hash=source_hash, preview=preview, counts=counts, checkpoint=True)
        result = confirm_preview(preview.pk, preview.snapshot_sha256, actor=actor,
                                 automation=(binding.pk, poll.lease_token))
        counts.update({k: result.run.summary[k] for k in ('processed', 'awarded', 'issued', 'skipped', 'failed')})
        failed = counts['failed'] > 0
        error = result.run.summary['errors'][0]['code'] if failed else ''
        return _finish(binding, poll, state='FAILED' if failed else 'COMPLETED', error=error,
            source_hash=source_hash, preview=result, counts=counts, checkpoint=not failed)
    except Exception as exc:
        # Never persist provider messages, rows, source IDs, paths or credentials.
        code = (exc.code if isinstance(exc, ImportProblem) else 'GOOGLE_SOURCE_UNAVAILABLE' if isinstance(exc, SheetUnavailable)
                else 'AUTOMATION_ACTOR_UNAUTHORIZED' if isinstance(exc, PermissionDenied) else 'AUTOMATION_PROCESSING_FAILED')
        return _finish(binding, poll, state='FAILED', error=code, source_hash=source_hash, preview=preview, counts=counts)


def poll_due_sources(*, limit=10):
    require_postgres()
    if connection.in_atomic_block or type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('Poll outside transactions with a bounded source limit.')
    result = {'checked': 0, 'completed': 0, 'unchanged': 0, 'excluded': 0, 'failed': 0}
    for _ in range(limit):
        claimed = claim_source()
        if claimed is None:
            break
        result['checked'] += 1
        state = process_source(*claimed)
        result[state.lower()] += 1
    return result
