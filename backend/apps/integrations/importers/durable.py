"""Authorized spreadsheet rows reuse the completion inbox and domain services."""
from django.db import connection
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from apps.integrations.classroom_automation import receive, process_event, require_source
from apps.integrations.models import ImportRun, ClassroomSyncEvent
from .validators import validate_completion_record


def process_import(records, *, source, actor=None, run=None, finalize=True):
    require_source(source)
    if connection.in_atomic_block:
        raise ImproperlyConfigured('Imports require independently committed replay stages.')
    if not isinstance(records, list) or len(records) > 5000:
        raise ValueError('Invalid or oversized import batch.')
    run = run or ImportRun.objects.create(source=source, actor=actor)
    result = {'processed': 0, 'awarded': 0, 'issued': 0, 'skipped': 0, 'failed': 0, 'errors': [], 'import_id': run.pk}
    for index, raw in enumerate(records, start=2):
        result['processed'] += 1
        try:
            record = validate_completion_record(raw)
            payload = {
                'source': source, 'event_id': record['source_event_id'],
                'student_id': record['external_student_id'], 'course_id': record['course_id'],
                'completion_status': record['completion_status'], 'completion_date': record['completion_date'],
                'grade': float(record['grade']), 'passed': record['passed'],
            }
            event_id = receive(payload, source=source, actor=actor)
            run.events.add(event_id)  # Link before processing; interrupted runs remain inspectable.
            outcome = process_event(event_id)
            result[outcome] += 1
            event = ClassroomSyncEvent.objects.get(pk=event_id)
            if outcome == 'issued':
                result['awarded'] += event.achievement_event.achievements.count()
            if outcome == 'failed':
                result['errors'].append({'row': index, 'type': event.error_code})
        except Exception as exc:
            result['failed'] += 1
            result['errors'].append({'row': index, 'type': type(exc).__name__})
    if finalize:
        run.summary = result
        run.state = 'PARTIAL' if result['failed'] and (result['issued'] or result['skipped']) else ('FAILED' if result['failed'] else 'COMPLETED')
        run.finished_at = timezone.now()
        run.save()
    return result


def reconcile_run(run):
    """Refresh derived progress after a restart/retry without fetching external rows."""
    states = list(run.events.values_list('state', flat=True))
    if not states:
        if run.state == 'RUNNING':
            run.state = 'FAILED'
            run.summary['error'] = 'INTERRUPTED_BEFORE_EVENT_RECEIPT'
    else:
        issued = states.count('CREDENTIAL_ISSUED')
        failed = states.count('FAILED')
        pending = len(states) - issued - failed
        run.summary.update(current_issued=issued, current_failed=failed, current_pending=pending)
        run.state = 'RUNNING' if pending else ('PARTIAL' if issued and (failed or run.validation_errors) else ('FAILED' if failed or run.validation_errors else 'COMPLETED'))
    if run.state != 'RUNNING':
        run.finished_at = timezone.now()
    run.save()
