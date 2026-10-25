import hashlib
import json
import random
import time
from datetime import datetime, timezone
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.utils.module_loading import import_string

from .models import Credential, CredentialAchievement, CredentialIssuer, CredentialLifecycleEvent
from apps.skills.models import VerifiedAchievement

DEFAULT_MAX_ACHIEVEMENTS = 256
MAX_IDEMPOTENCY_KEY = 255
MAX_ISSUER_REFERENCE = 255
MAX_REVOCATION_REASON = 2000
RETRY_ATTEMPTS = 3

class IdempotencyConflict(Exception):
    pass


def _fingerprint(achievement_ids, expires_at, supplied_issued_at):
    payload = json.dumps({"achievement_ids": [str(value) for value in achievement_ids], "expires_at": expires_at.isoformat() if expires_at else None, "issued_at": supplied_issued_at.isoformat() if supplied_issued_at else None}, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _validate_text(name, value, max_length):
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise ValidationError({name: f"Must be non-empty and at most {max_length} characters."})
    return value.strip()


def _retryable(exc):
    cause = exc.__cause__ or exc
    return (getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)) in {"40001", "40P01"}


def _retry(operation):
    if connection.in_atomic_block:
        return operation()
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return operation()
        except DatabaseError as exc:
            if not _retryable(exc) or attempt == RETRY_ATTEMPTS - 1:
                raise
            time.sleep(random.uniform(0.005, 0.025) * (attempt + 1))


def issue_credential(*, issuer_reference, idempotency_key, achievement_ids, expires_at=None, issued_at=None):
    max_achievements = int(getattr(settings, "CREDENTIAL_MAX_ACHIEVEMENTS", DEFAULT_MAX_ACHIEVEMENTS))
    if max_achievements < 1:
        raise ImproperlyConfigured("CREDENTIAL_MAX_ACHIEVEMENTS must be a positive integer.")
    issuer_reference = _validate_text("issuer_reference", issuer_reference, MAX_ISSUER_REFERENCE)
    idempotency_key = _validate_text("idempotency_key", idempotency_key, MAX_IDEMPOTENCY_KEY)
    try:
        raw_ids = tuple(achievement_ids)
        ids = tuple(sorted({UUID(str(value)) for value in raw_ids}, key=str))
        if not ids or len(ids) != len(raw_ids) or len(ids) > max_achievements:
            raise ValueError
    except (TypeError, ValueError, AttributeError):
        raise ValidationError({"achievement_ids": f"Provide 1 to {max_achievements} unique UUIDs."}) from None
    supplied_issued_at = issued_at
    issued_at = issued_at or datetime.now(timezone.utc)
    if issued_at.tzinfo is None or (expires_at is not None and (expires_at.tzinfo is None or expires_at <= issued_at)):
        raise ValidationError({"expires_at": "Dates must be timezone-aware and expiry later than issue time."})
    fingerprint = _fingerprint(ids, expires_at, supplied_issued_at)

    def operation():
        with transaction.atomic():
            existing = Credential.objects.select_for_update().filter(issuer_reference=issuer_reference, idempotency_key=idempotency_key).first()
            if existing:
                if existing.request_sha256 != fingerprint:
                    raise IdempotencyConflict("This idempotency key was used for a different request.")
                return existing
            achievements = list(VerifiedAchievement.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
            if len(achievements) != len(ids):
                raise ValidationError({"achievement_ids": "One or more achievements do not exist."})
            student_id = achievements[0].student_id
            if any(row.student_id != student_id for row in achievements):
                raise ValidationError({"achievement_ids": "All achievements must belong to the same student."})
            if any(row.verification_status != VerifiedAchievement.VerificationStatus.VERIFIED for row in achievements):
                raise ValidationError({"achievement_ids": "Only verified achievements can be credentialed."})
            issuer = CredentialIssuer.objects.get(reference=issuer_reference)
            credential = Credential.objects.create(student_id=student_id, issuer=issuer, issuer_reference=issuer.reference, issuer_name=issuer.display_name, idempotency_key=idempotency_key, request_sha256=fingerprint, issued_at=issued_at, expires_at=expires_at)
            CredentialAchievement.objects.bulk_create([CredentialAchievement(credential=credential, achievement=row) for row in achievements])
            CredentialLifecycleEvent.objects.create(credential=credential, event_type="ISSUED", occurred_at=issued_at, actor_reference=issuer.reference)
            return credential
    try:
        return _retry(operation)
    except IntegrityError:
        existing = Credential.objects.filter(issuer_reference=issuer_reference, idempotency_key=idempotency_key).first()
        if existing and existing.request_sha256 == fingerprint:
            return existing
        if existing:
            raise IdempotencyConflict("This idempotency key was used for a different request.") from None
        raise


def _revocation_actor(actor, credential):
    path = getattr(settings, "CREDENTIAL_REVOCATION_AUTHORIZER", None)
    if not path:
        raise ImproperlyConfigured("Credential revocation is disabled until an authorization policy is configured.")
    policy = import_string(path) if isinstance(path, str) else path
    return _validate_text("actor_reference", policy(actor, credential), 255)


def revoke_credential(*, public_reference, actor, reason):
    reason = _validate_text("reason", reason, 2000)
    credential = Credential.objects.get(public_reference=UUID(str(public_reference)))
    actor_reference = _revocation_actor(actor, credential)
    def operation():
        with transaction.atomic():
            locked = Credential.objects.select_for_update().get(pk=credential.pk)
            if locked.status == Credential.Status.REVOKED:
                if locked.revoked_by == actor_reference and locked.revocation_reason == reason:
                    return locked
                raise ValidationError("Credential has already been revoked with different details.")
            now = datetime.now(timezone.utc)
            locked.status, locked.revoked_at, locked.revoked_by, locked.revocation_reason = Credential.Status.REVOKED, now, actor_reference, reason
            locked.save(update_fields=["status", "revoked_at", "revoked_by", "revocation_reason"])
            CredentialLifecycleEvent.objects.create(credential=locked, event_type="REVOKED", occurred_at=now, actor_reference=actor_reference, reason=reason)
            return locked
    return _retry(operation)
