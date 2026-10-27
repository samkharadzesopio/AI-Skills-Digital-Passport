"""Institution-approved identity replacement; no PDF/RPC inside its transaction."""
import hashlib
import json
import unicodedata

from django.conf import settings
from django.core.exceptions import ValidationError, ImproperlyConfigured
from apps.blockchain.chain import ProofError
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.authorization import require_admin_permission
from apps.students.models import Student
from .models import DigitalPassport, PassportLifecycleEvent
from .services import publish_passport_version


class PassportLifecycleConflict(Exception):
    pass


def _text(value, maximum):
    if not isinstance(value, str):
        raise ValidationError('Invalid institutional identity correction.')
    value = unicodedata.normalize('NFC', ' '.join(value.split()))
    if not value or len(value) > maximum or not value.isprintable():
        raise ValidationError('Invalid institutional identity correction.')
    return value


def change_legal_name(*, actor, student_id, expected_passport_reference, first_name, last_name,
                      idempotency_key, evidence_source, evidence_reference, reason):
    require_admin_permission(actor, 'accounts.manage_legal_identity')
    first_name, last_name = _text(first_name,150), _text(last_name,150)
    evidence_reference, reason = _text(evidence_reference,200), _text(reason,500)
    idempotency_key = _text(idempotency_key,200)
    approved = getattr(settings, 'PASSPORT_IDENTITY_EVIDENCE_SOURCES', ())
    if not isinstance(approved,(list,tuple)) or evidence_source not in approved:
        raise ValidationError('Only approved institutional identity evidence is accepted.')
    payload = {'expected':str(expected_passport_reference), 'first':first_name, 'last':last_name,
               'evidence_source':evidence_source, 'evidence_reference':evidence_reference, 'reason':reason}
    fingerprint = hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
    with transaction.atomic():
        student = Student.objects.select_for_update().get(pk=student_id)
        prior = PassportLifecycleEvent.objects.filter(student=student,idempotency_key=idempotency_key).first()
        if prior:
            if prior.payload_sha256 != fingerprint or prior.event_type != 'NAME_CHANGE':
                raise PassportLifecycleConflict('This request key already represents another action.')
            return prior
        old = DigitalPassport.objects.select_for_update().get(student=student,status='ACTIVE')
        if str(old.public_reference) != str(expected_passport_reference):
            raise PassportLifecycleConflict('The current Passport changed; review before retrying.')
        previous_names=old.legal_name_snapshot or {'first_name':student.first_name,'last_name':student.last_name}
        if first_name == previous_names.get('first_name') and last_name == previous_names.get('last_name'):
            raise ValidationError('The legal name has not changed.')
        # A DB guard also requires the request-scoped, explicitly permissioned actor.
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.passport_lifecycle_actor', %s, true)", [str(actor.pk)])
        old.status, old.cancelled_at = 'REPLACED', timezone.now()
        old.save(update_fields=['status','cancelled_at','updated_at'])
        student.first_name, student.last_name = first_name, last_name
        student.save(update_fields=['first_name','last_name','updated_at'])
        new = DigitalPassport.objects.create(student=student,replaces=old,legal_name_snapshot={'first_name':first_name,'last_name':last_name})
        event = PassportLifecycleEvent.objects.create(
            student=student, previous=old, replacement=new, event_type='NAME_CHANGE',
            idempotency_key=idempotency_key,payload_sha256=fingerprint,approved_by=actor,
            evidence_source=evidence_source,evidence_reference=evidence_reference,reason=reason,
            legal_names={'previous':previous_names,'replacement':new.legal_name_snapshot},
        )
        from apps.blockchain.services import enqueue_replacement
        try:
            enqueue_replacement(old,new,event)
        except (ProofError,ImproperlyConfigured):
            # Approval/cancellation must not be undone by a missing chain target
            # or quarantined issuer. The worker recovers from this durable event.
            pass
        publish_passport_version(student_id=student.pk,event_key=f'legal-name-change:{event.pk}')
        new.refresh_from_db()
        return event


def revoke_passport(*, actor, passport_reference, idempotency_key, reason):
    require_admin_permission(actor, 'accounts.manage_passport_lifecycle')
    reason, idempotency_key = _text(reason,500), _text(idempotency_key,200)
    initial = DigitalPassport.objects.only('student_id').get(public_reference=passport_reference)
    fingerprint = hashlib.sha256(json.dumps({'passport':str(passport_reference),'reason':reason},sort_keys=True).encode()).hexdigest()
    with transaction.atomic():
        Student.objects.select_for_update().get(pk=initial.student_id)
        prior = PassportLifecycleEvent.objects.filter(student_id=initial.student_id,idempotency_key=idempotency_key).first()
        if prior:
            if prior.payload_sha256 != fingerprint or prior.event_type != 'REVOCATION':
                raise PassportLifecycleConflict('This request key already represents another action.')
            return prior
        passport = DigitalPassport.objects.select_for_update().get(public_reference=passport_reference)
        if passport.status != 'ACTIVE':
            raise PassportLifecycleConflict('Only an active Passport can be revoked.')
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.passport_lifecycle_actor', %s, true)",[str(actor.pk)])
        passport.status, passport.cancelled_at = 'REVOKED', timezone.now()
        passport.save(update_fields=['status','cancelled_at','updated_at'])
        event = PassportLifecycleEvent.objects.create(student_id=passport.student_id, previous=passport,
            event_type='REVOCATION',idempotency_key=idempotency_key,payload_sha256=fingerprint,
            approved_by=actor,evidence_source='BTU_ADMIN',evidence_reference=str(actor.pk),reason=reason)
        from apps.blockchain.services import enqueue_revocation
        try:
            enqueue_revocation(passport,event)
        except (ProofError,ImproperlyConfigured):
            pass
        return event
