import hashlib
import json
import random
import time
from datetime import datetime, timezone
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import DatabaseError, connection, transaction
from django.db.models import Prefetch, Q

from apps.credentials.models import (
    Credential,
    CredentialAchievement,
    CredentialLifecycleEvent,
    CredentialPassportRefresh,
)
from apps.students.models import Student

from .models import (
    DigitalPassport,
    PassportUpdateEvent,
    PassportVersion,
    PassportVersionCredential,
    PassportVersionCredentialSkill,
    PassportVersionSkill,
    PassportPublication,
)

MAX_EVENT_KEY_LENGTH = 255
RETRY_ATTEMPTS = 3


def _retryable(exc):
    cause = exc.__cause__ or exc
    code = getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)
    return code in {"40001", "40P01"}


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


def _event_key(value):
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_EVENT_KEY_LENGTH:
        raise ValidationError(
            {"event_key": f"Must be non-empty and at most {MAX_EVENT_KEY_LENGTH} characters."}
        )
    return value.strip()


def _student_snapshot(student):
    return {
        "external_student_id": student.external_student_id,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "email": student.email,
        "program": student.program,
        "education_level": student.education_level,
        "student_status": student.student_status,
    }


def _current_credential_rows(student_id, effective_at):
    achievement_links = CredentialAchievement.objects.select_related(
        "achievement__skill"
    ).order_by("achievement_id")
    credentials = (
        Credential.objects.select_for_update()
        .filter(
            student_id=student_id,
            status=Credential.Status.ISSUED,
            issued_at__lte=effective_at,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=effective_at))
        .prefetch_related(Prefetch("achievement_links", queryset=achievement_links))
        .order_by("pk")
    )
    return list(credentials)


def _snapshot_payload(student_snapshot, credentials):
    credential_payloads = []
    for credential in credentials:
        skills = {}
        for link in credential.achievement_links.all():
            skill = link.achievement.skill
            skills[str(skill.pk)] = {
                    "id": str(skill.pk),
                    "skill_code": skill.skill_code,
                    "skill_name": skill.skill_name,
                    "category": skill.category,
                    "subcategory": skill.subcategory,
                    "description": skill.description,
                    "stamp_type": skill.stamp_type,
                    "badge_asset_id": skill.badge_asset_id,
                }
        credential_payloads.append(
            {
                "id": str(credential.pk),
                "public_reference": str(credential.public_reference),
                "issuer_reference": credential.issuer_reference,
                "issuer_name": credential.issuer_name,
                "issued_at": credential.issued_at.isoformat(),
                "expires_at": (
                    credential.expires_at.isoformat() if credential.expires_at else None
                ),
                "skills": [skills[key] for key in sorted(skills)],
            }
        )
    payload = {
        "student": student_snapshot,
        "credentials": credential_payloads,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return payload, hashlib.sha256(canonical).hexdigest()


def get_or_create_passport(*, student_id):
    """Return the permanent passport, serializing concurrent creation by student."""

    student_uuid = UUID(str(student_id))

    def operation():
        with transaction.atomic():
            student = Student.objects.select_for_update().only("id").get(pk=student_uuid)
            try:
                passport = DigitalPassport.objects.get(student_id=student.pk, status='ACTIVE')
                return passport, False
            except DigitalPassport.DoesNotExist:
                if DigitalPassport.objects.filter(student_id=student.pk).exists():
                    raise ValidationError('A cancelled Passport requires explicit institutional replacement.')
                return DigitalPassport.objects.create(student_id=student.pk), True

    return _retry(operation)


def publish_passport_version(
    *, student_id, event_key, effective_at=None, source_occurred_at=None
):
    """Publish or reuse an immutable snapshot for one logical update event."""

    student_uuid = UUID(str(student_id))
    event_key = _event_key(event_key)
    effective_at = effective_at or datetime.now(timezone.utc)
    if effective_at.tzinfo is None:
        raise ValidationError({"effective_at": "Must be timezone-aware."})
    if source_occurred_at is not None and source_occurred_at.tzinfo is None:
        raise ValidationError({"source_occurred_at": "Must be timezone-aware."})

    def operation():
        with transaction.atomic():
            student = (
                Student.objects.select_for_update()
                .only(
                    "id",
                    "external_student_id",
                    "first_name",
                    "last_name",
                    "email",
                    "program",
                    "education_level",
                    "student_status",
                )
                .get(pk=student_uuid)
            )
            passport = (
                DigitalPassport.objects.select_for_update(of=("self",))
                .select_related("latest_version")
                .filter(student_id=student.pk,status='ACTIVE').first()
            )
            if passport is None:
                if DigitalPassport.objects.filter(student_id=student.pk).exists():
                    raise ValidationError('A cancelled Passport requires explicit institutional replacement.')
                passport=DigitalPassport.objects.create(student=student)

            prior_event = (
                PassportUpdateEvent.objects.select_related("version")
                .filter(passport=passport, event_key=event_key)
                .first()
            )
            if prior_event:
                return prior_event.version, False

            credentials = _current_credential_rows(student.pk, effective_at)
            if not passport.latest_version_id and not credentials:
                from apps.skills.models import VerifiedAchievement
                if not VerifiedAchievement.objects.filter(
                    student_id=student.pk, verification_status='VERIFIED',
                ).exists():
                    raise ValidationError('An initial Passport requires approved learning evidence.')
            student_snapshot = _student_snapshot(student)
            if passport.legal_name_snapshot:
                student_snapshot.update(passport.legal_name_snapshot)
            else:
                passport.legal_name_snapshot = {key: student_snapshot[key] for key in ('first_name','last_name')}
            payload, content_sha256 = _snapshot_payload(student_snapshot, credentials)

            if (
                passport.latest_version_id
                and passport.latest_version.content_sha256 == content_sha256
            ):
                version = passport.latest_version
                PassportUpdateEvent.objects.create(
                    passport=passport,
                    version=version,
                    event_key=event_key,
                    content_sha256=content_sha256,
                    source_occurred_at=source_occurred_at,
                )
                return version, False

            version_number = (
                passport.latest_version.version_number + 1
                if passport.latest_version_id
                else 1
            )
            version = PassportVersion.objects.create(
                passport=passport,
                version_number=version_number,
                student_snapshot=payload["student"],
            )

            credential_snapshots = []
            unique_skills = {}
            credential_skills = {}
            for credential in credentials:
                credential_snapshots.append(
                    PassportVersionCredential(
                        version=version,
                        credential=credential,
                        credential_public_reference=credential.public_reference,
                        issuer_reference=credential.issuer_reference,
                        issuer_name=credential.issuer_name,
                        credential_issued_at=credential.issued_at,
                        credential_expires_at=credential.expires_at,
                    )
                )
                skill_ids = set()
                for link in credential.achievement_links.all():
                    skill = link.achievement.skill
                    unique_skills[skill.pk] = skill
                    skill_ids.add(skill.pk)
                credential_skills[credential.pk] = skill_ids

            PassportVersionCredential.objects.bulk_create(credential_snapshots)
            skill_snapshots = [
                PassportVersionSkill(
                    version=version,
                    skill=skill,
                    skill_code=skill.skill_code,
                    skill_name=skill.skill_name,
                    category=skill.category,
                    subcategory=skill.subcategory,
                    description=skill.description,
                    stamp_type=skill.stamp_type,
                    badge_asset_id=skill.badge_asset_id,
                )
                for _, skill in sorted(unique_skills.items(), key=lambda item: str(item[0]))
            ]
            PassportVersionSkill.objects.bulk_create(skill_snapshots)

            credential_snapshot_by_id = {
                row.credential_id: row for row in credential_snapshots
            }
            skill_snapshot_by_id = {row.skill_id: row for row in skill_snapshots}
            PassportVersionCredentialSkill.objects.bulk_create(
                [
                    PassportVersionCredentialSkill(
                        credential_snapshot=credential_snapshot_by_id[credential_id],
                        skill_snapshot=skill_snapshot_by_id[skill_id],
                    )
                    for credential_id, skill_ids in credential_skills.items()
                    for skill_id in skill_ids
                ]
            )

            version.status = PassportVersion.Status.ISSUED
            version.issued_at = effective_at
            version.content_sha256 = content_sha256
            version.save(update_fields=["status", "issued_at", "content_sha256"])
            passport.latest_version = version
            passport.first_issued_at = passport.first_issued_at or effective_at
            passport.save(update_fields=["latest_version", "updated_at", "legal_name_snapshot", "first_issued_at"])
            # This version is newly created and not visible outside this transaction.
            PassportPublication.objects.create(version=version)
            PassportUpdateEvent.objects.create(
                passport=passport,
                version=version,
                event_key=event_key,
                content_sha256=content_sha256,
                source_occurred_at=source_occurred_at,
            )
            return version, True

    return _retry(operation)


def publish_passport_for_credential_event(*, lifecycle_event_id):
    """Refresh from current credential state while retaining the source event time."""

    event = CredentialLifecycleEvent.objects.select_related("credential").get(
        pk=UUID(str(lifecycle_event_id))
    )
    return publish_passport_version(
        student_id=event.credential.student_id,
        event_key=f"credential-lifecycle:{event.pk}",
        effective_at=datetime.now(timezone.utc),
        source_occurred_at=event.occurred_at,
    )


def schedule_passport_update_for_credential_event(*, lifecycle_event_id):
    """Persist an outbox event and request immediate post-commit processing."""

    try:
        max_attempts = int(getattr(settings, "PASSPORT_REFRESH_MAX_ATTEMPTS", 8))
    except (TypeError, ValueError):
        raise ImproperlyConfigured(
            "PASSPORT_REFRESH_MAX_ATTEMPTS must be an integer from 1 through 50."
        ) from None
    if not 1 <= max_attempts <= 50:
        raise ImproperlyConfigured(
            "PASSPORT_REFRESH_MAX_ATTEMPTS must be an integer from 1 through 50."
        )

    event_id = UUID(str(lifecycle_event_id))
    event = CredentialLifecycleEvent.objects.select_related("credential").get(pk=event_id)
    event_key = f"credential-lifecycle:{event.pk}"
    refresh, _ = CredentialPassportRefresh.objects.get_or_create(
        event_key=event_key,
        defaults={
            "source_type": CredentialPassportRefresh.SourceType.CREDENTIAL_LIFECYCLE,
            "student_id": event.credential.student_id,
            "lifecycle_event": event,
            "source_occurred_at": event.occurred_at,
            "available_at": datetime.now(timezone.utc),
            "max_attempts": max_attempts,
        },
    )
    if (
        refresh.source_type != CredentialPassportRefresh.SourceType.CREDENTIAL_LIFECYCLE
        or refresh.lifecycle_event_id != event.pk
        or refresh.student_id != event.credential.student_id
        or refresh.source_occurred_at != event.occurred_at
    ):
        raise ValidationError("Credential lifecycle refresh identity does not match its source event.")

    def process_after_commit():
        from apps.credentials.passport_refresh import process_passport_refresh_event

        process_passport_refresh_event(refresh_id=refresh.pk)

    transaction.on_commit(
        process_after_commit,
        robust=True,
    )
    return refresh
