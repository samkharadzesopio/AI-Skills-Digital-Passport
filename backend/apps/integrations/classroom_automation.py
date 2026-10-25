"""Trusted simulated source -> durable inbox -> existing domain services.

No external IO or Passport publication is performed under inbox locks.
"""
import hashlib
import json
import math
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import connection, transaction
from django.utils import timezone

from apps.credentials.models import BTU_ISSUER_REFERENCE, Credential, CredentialIssuer
from apps.credentials.services import IdempotencyConflict, issue_credential
from apps.skills.achievement_services import SourceEventConflict
from apps.skills.models import AchievementSourceEvent, Skill
from apps.students.models import Student
from .achievement_adapter import award_classroom_skills
from .importers.validators import ImportValidationError, validate_completion_record
from .models import ClassroomSyncEvent as Event
from .repositories import ApprovedAICourseRepository
from .services import ClassroomService

SOURCE = 'BTU_CLASSROOM'
MAX_ATTEMPTS = 5


class EventConflict(ValueError):
    pass


class RecognitionError(ValueError):
    pass


def fingerprint(payload):
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except (ValueError, TypeError):
        raise RecognitionError('INVALID_PAYLOAD') from None
    if len(encoded.encode()) > 16_384:
        raise RecognitionError('PAYLOAD_TOO_LARGE')
    return hashlib.sha256(encoded.encode()).hexdigest()


def idempotency_key(event_id, source=SOURCE):
    return ('classroom:v1:' if source == SOURCE else 'completion:v1:') + hashlib.sha256(
        json.dumps([source, event_id], separators=(',', ':')).encode()
    ).hexdigest()


def require_postgres():
    if connection.vendor != 'postgresql':
        raise ImproperlyConfigured('Classroom automation requires PostgreSQL row locking.')


def configured_issuer():
    ref = getattr(settings, 'BTU_CLASSROOM_ISSUER_REFERENCE', None)
    if ref != BTU_ISSUER_REFERENCE:
        raise ImproperlyConfigured('Classroom credentials must use the fixed BTU-UNIVERSITY issuer.')
    if not CredentialIssuer.objects.filter(reference=BTU_ISSUER_REFERENCE, is_trusted=True).exists():
        raise ImproperlyConfigured('The trusted BTU issuer must be provisioned first.')
    return BTU_ISSUER_REFERENCE


def require_source(source):
    if source == SOURCE:
        return
    approved = getattr(settings, 'BTU_AUTHORIZED_COMPLETION_SOURCES', ())
    if source not in ('BTU_EXCEL', 'BTU_GOOGLE_SHEETS') or not isinstance(approved, (list, tuple)) or source not in approved:
        raise RecognitionError('UNAUTHORIZED_INSTITUTIONAL_SOURCE')


def recognize(record):
    if not isinstance(record, dict):
        raise RecognitionError('INVALID_PAYLOAD')
    require_source(record.get('source', SOURCE))
    normalized = validate_completion_record({
        **record,
        'external_student_id': record.get('student_id'),
        'source_event_id': record.get('event_id'),
    })
    matches = [c for c in ApprovedAICourseRepository().get_approved_courses()
               if c.get('course_id') == normalized['course_id']]
    if len(matches) != 1:
        raise RecognitionError('UNAPPROVED_OR_AMBIGUOUS_COURSE')
    course = matches[0]
    threshold = course.get('minimum_grade')
    codes = course.get('skill_codes')
    if course.get('enabled', True) is not True:
        raise RecognitionError('COURSE_DISABLED')
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 100:
        raise RecognitionError('INVALID_PASSING_RULE')
    if normalized['grade'] < threshold:
        raise RecognitionError('BELOW_PASSING_GRADE')
    if not isinstance(codes, list) or not codes or any(
        not isinstance(c, str) or not c or c != c.strip() for c in codes
    ) or len(set(codes)) != len(codes):
        raise RecognitionError('INVALID_SKILL_MAPPING')
    if not Student.objects.filter(external_student_id=normalized['external_student_id']).exists():
        raise RecognitionError('UNKNOWN_STUDENT')
    if Skill.objects.filter(skill_code__in=codes).count() != len(codes):
        raise RecognitionError('UNKNOWN_SKILL')
    mapping = {'course_id': normalized['course_id'], 'skill_codes': sorted(codes), 'minimum_grade': threshold}
    return mapping


@transaction.atomic
def receive(record, *, actor=None, source=SOURCE):
    require_postgres()
    if not isinstance(record, dict):
        raise RecognitionError('INVALID_PAYLOAD')
    require_source(source)
    if record.get('source', source) != source:
        raise RecognitionError('UNTRUSTED_SOURCE')
    event_id = record.get('event_id')
    if not isinstance(event_id, str) or not event_id or event_id != event_id.strip() or len(event_id) > 120:
        raise RecognitionError('INVALID_EVENT_ID')
    hashed = fingerprint(record)
    event, _ = Event.objects.get_or_create(
        source=source, source_event_id=event_id,
        defaults={'payload': record, 'payload_sha256': hashed, 'requested_by': actor},
    )
    if event.payload_sha256 != hashed:
        raise EventConflict('EVENT_PAYLOAD_CONFLICT')
    return event.pk


def _validate_frozen(event):
    mapping = recognize(event.payload)
    issuer = configured_issuer()
    if event.mapping_snapshot is not None and (event.mapping_snapshot != mapping or event.issuer_reference != issuer):
        raise EventConflict('MAPPING_OR_ISSUER_CHANGED')
    return mapping, issuer


def _record_achievements(event_id, force):
    with transaction.atomic():
        event = Event.objects.select_for_update().get(pk=event_id)
        if event.state == Event.State.CREDENTIAL_ISSUED:
            return False
        now = timezone.now()
        if event.attempts >= MAX_ATTEMPTS or (not force and event.state == Event.State.FAILED and (
            not event.retryable or (event.next_retry_at and event.next_retry_at > now)
        )):
            return False
        event.attempts += 1
        # Persist attempts even when domain validation/achievement persistence fails.
        event.state = Event.State.PROCESSING
        event.save()
        try:
            with transaction.atomic():
                mapping, issuer = _validate_frozen(event)
                award_classroom_skills(event.payload, mapping['skill_codes'], source=event.source)
                source_event = AchievementSourceEvent.objects.get(source=event.source, source_event_id=event.source_event_id)
        except Exception as exc:
            _set_failure(event, exc)
            event.save()
            return False
        event.mapping_snapshot = mapping
        event.issuer_reference = issuer
        event.achievement_event = source_event
        event.state = Event.State.ACHIEVEMENTS_RECORDED
        event.error_code, event.retryable, event.next_retry_at = '', False, None
        event.save()
        return True


def _set_failure(event, exc):
    # Persist classifications only: provider/DB exception text can contain private data.
    permanent = isinstance(exc, (RecognitionError, EventConflict, ImportValidationError,
                                  ValidationError, SourceEventConflict, IdempotencyConflict))
    event.error_code = type(exc).__name__
    if isinstance(exc, RecognitionError):
        event.error_code = str(exc)
    event.state = Event.State.FAILED
    event.retryable = not permanent and event.attempts < MAX_ATTEMPTS
    event.next_retry_at = timezone.now() + timedelta(seconds=min(3600, 30 * 2 ** event.attempts)) if event.retryable else None


def process_event(event_id, *, force=False):
    require_postgres()
    if connection.in_atomic_block:
        raise ImproperlyConfigured('Inbox stages require autocommit; do not wrap processing in an outer transaction.')
    stage = 'achievements'
    try:
        if not _record_achievements(event_id, force):
            event = Event.objects.get(pk=event_id)
            return 'skipped' if event.state == Event.State.CREDENTIAL_ISSUED else 'failed'
        stage = 'credential'
        with transaction.atomic():
            event = Event.objects.select_for_update().get(pk=event_id)
            if event.state == Event.State.CREDENTIAL_ISSUED:
                return 'skipped'
            _validate_frozen(event)
            # Always replay the achievement service: it validates receipt contents,
            # and returns the same UUIDs after a prior partial completion.
            outcome = award_classroom_skills(event.payload, event.mapping_snapshot['skill_codes'], source=event.source)
            key = idempotency_key(event.source_event_id, event.source)
            existed = Credential.objects.filter(issuer_reference=event.issuer_reference, idempotency_key=key).exists()
            event.credential = issue_credential(
                issuer_reference=event.issuer_reference, idempotency_key=key,
                achievement_ids=outcome['achievement_ids'],
            )
            event.state = Event.State.CREDENTIAL_ISSUED
            event.error_code, event.retryable, event.next_retry_at = '', False, None
            event.save()
            return 'skipped' if existed else 'issued'
    except Exception as exc:
        # Domain stage has rolled back; durably record failure in a new transaction.
        with transaction.atomic():
            event = Event.objects.select_for_update().get(pk=event_id)
            if event.state == Event.State.CREDENTIAL_ISSUED:
                return 'skipped'
            if stage == 'achievements':
                # A deadlock/serialization abort rolls back the attempt increment.
                event.attempts = min(MAX_ATTEMPTS, event.attempts + 1)
            _set_failure(event, exc)
            event.save()
        return 'failed'


class ClassroomCredentialAutomation:
    def __init__(self, classroom_service=None):
        self.classroom = classroom_service or ClassroomService()

    def synchronize(self, *, dry_run=True, actor=None):
        # The API accepts controls only. Events always come from this server adapter.
        if not dry_run:
            require_postgres()
            if connection.in_atomic_block:
                raise ImproperlyConfigured('Classroom sync requires autocommit transactions.')
        records = self.classroom.get_completions()
        if not isinstance(records, list) or len(records) > 5000:
            raise RecognitionError('INVALID_OR_OVERSIZED_BATCH')
        result = {'processed': 0, 'issued': 0, 'skipped': 0, 'failed': 0, 'would_issue': 0, 'eligible_count': 0, 'eligible_event_ids': [], 'errors': []}
        preview_seen = {}
        for record in records:
            result['processed'] += 1
            event_id = None
            try:
                if isinstance(record, dict) and record.get('source', SOURCE) != SOURCE:
                    raise RecognitionError('UNTRUSTED_CLASSROOM_PROVENANCE')
                if dry_run:
                    recognize(record)
                    configured_issuer()
                    hashed = fingerprint(record)
                    source_id = record['event_id']
                    if source_id in preview_seen:
                        if preview_seen[source_id] != hashed:
                            raise EventConflict('EVENT_PAYLOAD_CONFLICT')
                        result['skipped'] += 1
                        continue
                    preview_seen[source_id] = hashed
                    result['eligible_count'] += 1
                    result['eligible_event_ids'].append(record.get('event_id'))
                    existing = Event.objects.filter(source=SOURCE, source_event_id=record.get('event_id')).first()
                    if existing and existing.payload_sha256 != fingerprint(record):
                        raise EventConflict('EVENT_PAYLOAD_CONFLICT')
                    if existing and existing.state == Event.State.CREDENTIAL_ISSUED:
                        result['skipped'] += 1
                    else:
                        result['would_issue'] += 1
                    continue
                event_id = receive(record, actor=actor)
                outcome = process_event(event_id)
                result[outcome] += 1
                if outcome in ('issued', 'skipped'):
                    result['eligible_count'] += 1
                    result['eligible_event_ids'].append(record['event_id'])
                if outcome == 'failed':
                    result['errors'].append({'event_id': str(event_id), 'code': Event.objects.get(pk=event_id).error_code})
            except (EventConflict, RecognitionError, ImportValidationError, ImproperlyConfigured) as exc:
                result['failed'] += 1
                result['errors'].append({'event_id': str(event_id) if event_id else None, 'code': type(exc).__name__})
        return result
