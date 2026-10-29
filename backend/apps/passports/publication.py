"""Recoverable generation queue for issued immutable versions, outside transactions."""
import uuid
from datetime import timedelta
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from .models import PassportPublication, PassportVersion
from .document_services import generate_passport_document, DocumentGenerationInProgress


def process_publication(publication_id):
    if connection.in_atomic_block:
        raise RuntimeError('PDF publication cannot run inside a transaction.')
    token = uuid.uuid4()
    with transaction.atomic():
        row = PassportPublication.objects.select_for_update().select_related('version__passport').get(pk=publication_id)
        now = timezone.now()
        if row.state in ('COMPLETE','CANCELLED'):
            return row.state
        if row.version.passport.status != 'ACTIVE':
            row.state = 'CANCELLED'; row.save(update_fields=['state','updated_at']); return row.state
        if row.state == 'PROCESSING' and row.lease_expires_at and row.lease_expires_at > now:
            return 'PROCESSING'
        if row.attempts >= 10:
            return 'FAILED'
        row.state, row.lease_token = 'PROCESSING', token
        row.lease_expires_at = now + timedelta(seconds=180)
        row.save(update_fields=['state','lease_token','lease_expires_at','updated_at'])
        version_id = row.version_id
    try:
        document = generate_passport_document(passport_version_id=version_id,wait_seconds=0)
    except DocumentGenerationInProgress:
        document, error = None, 'GENERATION_IN_PROGRESS'
    except Exception:
        document, error = None, 'PDF_GENERATION_UNAVAILABLE'
    else:
        error = ''
    with transaction.atomic():
        row = PassportPublication.objects.select_for_update().get(pk=publication_id)
        if row.lease_token != token:
            return row.state
        row.lease_token, row.lease_expires_at = None, None
        row.error_code = error
        if document:
            row.state, row.document, row.next_attempt_at = 'COMPLETE', document, None
        else:
            row.attempts += 1
            row.state = 'FAILED' if row.attempts >= 10 else 'PENDING'
            row.next_attempt_at = timezone.now() + timedelta(seconds=min(300,5*2**row.attempts))
        row.save()
        return row.state


def process_publications(batch_size=20):
    now = timezone.now()
    for version in PassportVersion.objects.filter(status='ISSUED',passport__status='ACTIVE',publication__isnull=True).order_by('created_at')[:batch_size]:
        PassportPublication.objects.get_or_create(version=version)
    ids = list(PassportPublication.objects.filter(state__in=['PENDING','PROCESSING']).filter(
        Q(next_attempt_at__isnull=True)|Q(next_attempt_at__lte=now)
    ).filter(Q(lease_expires_at__isnull=True)|Q(lease_expires_at__lte=now)).order_by('created_at').values_list('pk',flat=True)[:batch_size])
    counts = {'processed':len(ids)}
    for pk in ids:
        state=process_publication(pk); counts[state]=counts.get(state,0)+1
    return counts
