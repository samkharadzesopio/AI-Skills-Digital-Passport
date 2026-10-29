"""Protected previews and replayable confirmation; existing domain ledgers remain authoritative."""
from datetime import date, timedelta
from uuid import uuid4

from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.authorization import require_admin_permission
from apps.credentials.services import issue_credential
from apps.integrations.classroom_automation import RecognitionError, configured_issuer, recognize, require_source
from apps.integrations.models import ImportRun, SpreadsheetAward, SpreadsheetPreview, SpreadsheetProfile
from apps.skills.achievement_services import record_verified_achievements
from apps.skills.models import AchievementSourceEvent, Skill
from apps.students.models import Student
from .durable import process_import
from .mapping import digest, map_grid, validate_definition
from .profiles import profile_hash
from .sheet_source import read_profile_sheet
from .validators import ImportValidationError


class ImportProblem(ImportValidationError):
    def __init__(self, code, status=409):
        self.code, self.status = code, status
        super().__init__(code)


MESSAGES = {
    'ELIGIBLE': 'The record passed validation and can be included in the reviewed import.',
    'ALREADY_IMPORTED': 'This unchanged evidence has already issued a credential.',
    'DUPLICATE_IN_SOURCE': 'An identical Record ID occurs earlier in this source snapshot.',
    'CONFLICTING_RECORD_ID': 'The same Record ID has conflicting or invalid source rows. All copies are blocked.',
    'EVIDENCE_PAYLOAD_CONFLICT': 'This evidence identity was previously imported with different facts.',
    'INSTITUTIONAL_CONFIRMATION_REQUIRED': 'The source must explicitly record CONFIRMED. Pending, rejected or missing decisions cannot issue.',
    'UNKNOWN_STUDENT': 'The exact external Student ID is not registered. No Student will be created.',
    'UNKNOWN_SKILL': 'The approved Skill ID does not match an existing catalog entry.',
    'SKILL_NOT_AUTHORIZED': 'This Skill ID is outside the source policy allowlist.',
    'STUDENT_NOT_ELIGIBLE': 'The registered Student status is not eligible under this source policy.',
    'CANCELLED_PASSPORT_REQUIRES_REPLACEMENT': 'A cancelled Passport requires the existing institutional replacement process.',
    'STUDENT_IDENTITY_CONFLICT': 'Source identity fields conflict with the registered Student. Imports cannot edit identity.',
    'SKILL_CATALOG_CONFLICT': 'Source catalog metadata conflicts with the registered skill.',
    'MISSING_OR_INVALID_IDENTIFIER': 'A required Student, Record, Skill or course identifier is missing or invalid.',
    'INVALID_DATE': 'The earned/completion date is missing or invalid.',
    'INVALID_OR_AMBIGUOUS_DATE': 'The earned/completion date is invalid, ambiguous or in the future.',
    'FORMULA_NOT_ALLOWED': 'A mapped evidence field contains a spreadsheet formula.',
    'INVALID_COMPLETION_ROW': 'Completion evidence must include an exact completed/passed decision, finite grade and valid date.',
    'UNAPPROVED_OR_AMBIGUOUS_COURSE': 'The course does not have one approved recognition mapping.',
    'BELOW_PASSING_GRADE': 'The grade is below the approved course threshold.',
}


def check_profile(profile):
    if not profile.enabled or profile_hash(profile) != profile.definition_sha256:
        raise ImportProblem('SOURCE_PROFILE_DISABLED_OR_CHANGED', 503)
    validate_definition(profile.kind, profile.definition)
    try:
        require_source(profile.source)
        configured_issuer()
    except Exception:
        raise ImportProblem('INSTITUTIONAL_SOURCE_OR_ISSUER_NOT_CONFIGURED', 503) from None


def event_key(profile, record):
    # Version is intentionally excluded: a new mapping version cannot issue an old award again.
    return 'spreadsheet-award:v1:' + digest([profile.definition['evidence_namespace'], record['source_event_id']])


def completion_payload(profile, record):
    return {'source': profile.source, 'event_id': record['source_event_id'],
            'student_id': record['external_student_id'], 'course_id': record['course_id'],
            'completion_status': record['completion_status'], 'completion_date': record['completion_date'],
            'grade': float(record['grade']), 'passed': record['passed']}


def binding(profile, record, *, lock=False):
    students = Student.objects.select_for_update() if lock else Student.objects
    student = students.filter(external_student_id=record['external_student_id']).first()
    if student is None:
        raise ImportProblem('UNKNOWN_STUDENT')
    if (profile.kind == 'SKILL_AWARD' or 'approval_status' in profile.definition['columns']) and record.get('approval_status') != 'CONFIRMED':
        raise ImportProblem('INSTITUTIONAL_CONFIRMATION_REQUIRED')
    for field in ('first_name', 'last_name', 'email', 'student_status'):
        value = record.get(field)
        if value not in (None, '') and value != getattr(student, field):
            raise ImportProblem('STUDENT_IDENTITY_CONFLICT')
    if profile.kind == 'COMPLETION':
        try:
            mapping = recognize(completion_payload(profile, record))
        except RecognitionError as exc:
            raise ImportProblem(str(exc)) from None
        codes = mapping['skill_codes']
    else:
        if record.get('approval_status') != 'CONFIRMED':
            raise ImportProblem('INSTITUTIONAL_CONFIRMATION_REQUIRED')
        if student.student_status not in profile.definition['eligible_student_statuses']:
            raise ImportProblem('STUDENT_NOT_ELIGIBLE')
        from apps.passports.models import DigitalPassport
        identities = DigitalPassport.objects.filter(student=student)
        if identities.exists() and not identities.filter(status='ACTIVE').exists():
            raise ImportProblem('CANCELLED_PASSPORT_REQUIRES_REPLACEMENT')
        if record['skill_code'] not in profile.definition['allowed_skill_codes']:
            raise ImportProblem('SKILL_NOT_AUTHORIZED')
        codes, mapping = [record['skill_code']], None
    skills = list(Skill.objects.filter(skill_code__in=codes).order_by('skill_code'))
    if len(skills) != len(codes):
        raise ImportProblem('UNKNOWN_SKILL')
    if profile.kind == 'SKILL_AWARD':
        for field, attribute in [('skill_name', 'skill_name'), ('category', 'category'), ('stamp_type', 'stamp_type')]:
            value = record.get(field)
            if value not in (None, '') and value != getattr(skills[0], attribute):
                raise ImportProblem('SKILL_CATALOG_CONFLICT')
    return {'student_id': str(student.pk), 'skill_ids': [str(s.pk) for s in skills], 'mapping': mapping}


def receipt_status(profile, record):
    if profile.kind == 'SKILL_AWARD':
        existing = SpreadsheetAward.objects.filter(namespace=profile.definition['evidence_namespace'],
                                                    record_id=record['source_event_id']).first()
        if existing:
            if existing.payload_sha256 != digest(record):
                raise ImportProblem('EVIDENCE_PAYLOAD_CONFLICT')
            return 'DUPLICATE'
    else:
        from apps.integrations.classroom_automation import fingerprint
        from apps.integrations.models import ClassroomSyncEvent
        existing = ClassroomSyncEvent.objects.filter(source=profile.source, source_event_id=record['source_event_id']).first()
        if existing:
            if existing.payload_sha256 != fingerprint(completion_payload(profile, record)):
                raise ImportProblem('EVIDENCE_PAYLOAD_CONFLICT')
            if existing.state == 'CREDENTIAL_ISSUED':
                return 'DUPLICATE'
    return 'VALID'


def create_preview(profile, rows, source_hash, *, actor):
    require_admin_permission(actor, 'accounts.import_completions')
    check_profile(profile)
    mapped = map_grid(rows, kind=profile.kind, definition=profile.definition)
    issues = mapped['issues']
    planned, seen, conflicts = [], {}, set(mapped['invalid_event_ids'])
    for item in mapped['records']:
        key, hashed = item['record']['source_event_id'], digest(item['record'])
        if key in seen and seen[key] != hashed:
            conflicts.add(key)
        seen[key] = hashed
    seen.clear()
    for item in mapped['records']:
        record, number = item['record'], item['row']
        try:
            key = record['source_event_id']
            if key in conflicts:
                raise ImportProblem('CONFLICTING_RECORD_ID')
            if key in seen:
                issues.append({'row': number, 'status': 'DUPLICATE', 'code': 'DUPLICATE_IN_SOURCE'})
                continue
            seen[key] = True
            if (profile.kind == 'SKILL_AWARD' or 'approval_status' in profile.definition['columns']) and record.get('approval_status') != 'CONFIRMED':
                issues.append({'row': number, 'status': 'REVIEW', 'code': 'INSTITUTIONAL_CONFIRMATION_REQUIRED'})
                continue
            identities = binding(profile, record)
            state = receipt_status(profile, record)
            issues.append({'row': number, 'status': state, 'code': 'ELIGIBLE' if state == 'VALID' else 'ALREADY_IMPORTED'})
            if state == 'VALID':
                planned.append({**item, 'binding': identities})
        except ImportProblem as exc:
            issues.append({'row': number, 'status': 'INVALID', 'code': exc.code})
        except Exception:
            issues.append({'row': number, 'status': 'INVALID', 'code': 'DOMAIN_VALIDATION_FAILED'})
    for issue in issues:
        issue['message'] = MESSAGES.get(issue['code'], 'The row did not pass the approved source/domain validation rules.')
    report = {'profile_id': str(profile.pk), 'profile_key': profile.key, 'profile_version': profile.version,
              'kind': profile.kind, 'source': profile.source, 'header_row': mapped['header_row'],
              'columns': {k: v + 1 for k, v in mapped['columns'].items()}, 'total_rows': mapped['total_rows'],
              'valid_records': sum(r['status'] == 'VALID' for r in issues),
              'duplicate_records': sum(r['status'] == 'DUPLICATE' for r in issues),
              'invalid_records': sum(r['status'] == 'INVALID' for r in issues),
              'review_records': sum(r['status'] == 'REVIEW' for r in issues),
              'rows': sorted(issues, key=lambda x: x['row'])}
    now = timezone.now()
    snapshot = digest({'source_sha256': source_hash, 'profile_sha256': profile.definition_sha256,
                       'records': planned, 'report': report})
    return SpreadsheetPreview.objects.create(actor=actor, profile=profile, source_sha256=source_hash,
        snapshot_sha256=snapshot, records=planned, report=report, expires_at=now + timedelta(hours=1))


def public_preview(preview):
    return {'id': str(preview.pk), 'snapshot_sha256': preview.snapshot_sha256, 'state': preview.state,
            'expires_at': preview.expires_at, 'report': preview.report,
            'result': preview.run.summary if preview.run_id else None}


@transaction.atomic
def apply_award(profile_id, item, *, actor, automation=None):
    # Lock policy and Student for the entire award transaction. Profile disable and
    # identity lifecycle actions serialize against issuance; existing services own their guards.
    if automation is not None:
        from apps.integrations.spreadsheet_automation import require_automation_lease
        actor = require_automation_lease(*automation, profile_id, actor.pk)
    profile = SpreadsheetProfile.objects.select_for_update().get(pk=profile_id)
    check_profile(profile)
    record = item['record']
    if binding(profile, record, lock=True) != item['binding']:
        raise ImportProblem('PREVIEW_IDENTITY_OR_MAPPING_CHANGED')
    existing = SpreadsheetAward.objects.filter(namespace=profile.definition['evidence_namespace'],
                                                record_id=record['source_event_id']).first()
    if existing:
        if existing.payload_sha256 != digest(record):
            raise ImportProblem('EVIDENCE_PAYLOAD_CONFLICT')
        return existing, False
    key = event_key(profile, record)
    awards, _ = record_verified_achievements(source='BTU_SKILL_AWARD', source_event_id=key,
        external_student_id=record['external_student_id'], approved_skill_codes=[record['skill_code']],
        earned_on=date.fromisoformat(record['earned_on']), verification_status='VERIFIED',
        course_id='', evidence_reference=key, evidence={'kind': 'INSTITUTIONAL_SKILL_AWARD',
            'approval_status': 'CONFIRMED', 'approval_reference': record.get('approval_reference', ''),
            'record_sha256': digest(record)})
    credential = issue_credential(issuer_reference=configured_issuer(), idempotency_key=key,
                                  achievement_ids=[a.pk for a in awards])
    receipt = SpreadsheetAward.objects.create(source=profile.source, profile_key=profile.key,
        namespace=profile.definition['evidence_namespace'],
        record_id=record['source_event_id'], payload_sha256=digest(record), payload=record,
        profile=profile, achievement_event_id=awards[0].source_event_id, credential=credential, actor=actor)
    return receipt, True


def confirm_preview(preview_id, snapshot, *, actor, automation=None):
    require_admin_permission(actor, 'accounts.import_completions')
    if connection.in_atomic_block:
        raise ImportProblem('CONFIRMATION_REQUIRES_AUTOCOMMIT', 503)
    # Refetch Google data before claiming; changed remote content requires a new review.
    preview = SpreadsheetPreview.objects.select_related('profile').get(pk=preview_id, actor=actor)
    check_profile(preview.profile)
    if preview.snapshot_sha256 != snapshot:
        raise ImportProblem('PREVIEW_DIGEST_MISMATCH')
    if preview.state == 'COMPLETED':
        return preview
    if preview.expires_at <= timezone.now():
        raise ImportProblem('PREVIEW_EXPIRED')
    if preview.profile.source == 'BTU_GOOGLE_SHEETS':
        _, current_hash = read_profile_sheet(preview.profile)
        if current_hash != preview.source_sha256:
            raise ImportProblem('SOURCE_CHANGED_REVIEW_REQUIRED')
    with transaction.atomic():
        preview = SpreadsheetPreview.objects.select_for_update().get(pk=preview.pk, actor=actor)
        now = timezone.now()
        if preview.state == 'COMPLETED':
            return preview
        if preview.lease_until and preview.lease_until > now:
            raise ImportProblem('IMPORT_ALREADY_RUNNING')
        if preview.attempts >= 5 or preview.expires_at <= now:
            raise ImportProblem('PREVIEW_EXPIRED_OR_ATTEMPTS_EXHAUSTED')
        if not preview.records:
            raise ImportProblem('NO_ELIGIBLE_RECORDS')
        token = uuid4()
        preview.state, preview.lease_token = 'PROCESSING', token
        preview.attempts += 1
        preview.lease_until, preview.confirmed_at = now + timedelta(minutes=5), preview.confirmed_at or now
        if not preview.run_id:
            preview.run = ImportRun.objects.create(source=preview.profile.source, actor=actor)
        preview.save()
    result = {'processed': 0, 'awarded': 0, 'issued': 0, 'skipped': 0, 'failed': 0, 'errors': [], 'rows': [], 'import_id': preview.run_id}
    for item in preview.records:
        with transaction.atomic():
            owned = SpreadsheetPreview.objects.select_for_update().get(pk=preview.pk)
            if owned.lease_token != token:
                raise ImportProblem('IMPORT_LEASE_LOST')
            owned.lease_until = timezone.now() + timedelta(minutes=5)
            owned.save(update_fields=['lease_until'])
        result['processed'] += 1
        try:
            profile = SpreadsheetProfile.objects.get(pk=preview.profile_id)
            check_profile(profile)
            if profile.kind == 'SKILL_AWARD':
                receipt, created = apply_award(profile.pk, item, actor=actor, **({'automation': automation} if automation is not None else {}))
                result['issued' if created else 'skipped'] += 1
                result['awarded'] += int(created)
                result['rows'].append({'row': item['row'], 'status': 'ISSUED' if created else 'SKIPPED',
                    'receipt_id': str(receipt.pk), 'credential_id': str(receipt.credential_id)})
            else:
                if binding(profile, item['record']) != item['binding']:
                    raise ImportProblem('PREVIEW_IDENTITY_OR_MAPPING_CHANGED')
                # The existing inbox links rows to this one run. The enclosing
                # preview finalizes aggregate history, not each individual row.
                outcome = process_import([item['record']], source=profile.source, actor=actor,
                                         run=preview.run, finalize=False)
                for key in ('issued', 'skipped', 'failed'):
                    result[key] += outcome[key]
                result['awarded'] += outcome['awarded']
                result['rows'].append({'row': item['row'], 'status': 'FAILED' if outcome['failed'] else ('ISSUED' if outcome['issued'] else 'SKIPPED')})
                if outcome['failed']:
                    result['errors'].append({'row': item['row'], 'code': 'COMPLETION_PROCESSING_FAILED'})
        except Exception as exc:
            result['failed'] += 1
            result['errors'].append({'row': item['row'], 'code': exc.code if isinstance(exc, ImportProblem) else 'PROCESSING_FAILED'})
            result['rows'].append({'row': item['row'], 'status': 'FAILED'})
    with transaction.atomic():
        preview = SpreadsheetPreview.objects.select_for_update(of=('self',)).select_related('run').get(pk=preview.pk)
        if preview.lease_token != token:
            raise ImportProblem('IMPORT_LEASE_LOST')
        preview.run.summary = result
        preview.run.validation_errors = [r for r in preview.report['rows'] if r['status'] in ('INVALID', 'REVIEW')]
        preview.run.state = 'PARTIAL' if result['issued'] or result['skipped'] else 'FAILED'
        if not result['failed'] and not preview.run.validation_errors:
            preview.run.state = 'COMPLETED'
        preview.run.finished_at = timezone.now()
        preview.run.save()
        preview.state = 'FAILED' if result['failed'] else 'COMPLETED'
        preview.lease_until, preview.lease_token = None, None
        preview.save()
    return preview
