import hashlib
import json
import random
import time
from datetime import datetime, timezone
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.db.models import Prefetch, Q

from apps.credentials.models import (
    Credential,
    CredentialAchievement,
    CredentialLifecycleEvent,
)
from apps.students.models import Student

from .models import (
    DigitalPassport,
    PassportUpdateEvent,
    PassportVersion,
    PassportVersionCredential,
    PassportVersionCredentialSkill,
    PassportVersionSkill,
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
                passport = DigitalPassport.objects.get(student_id=student.pk)
                return passport, False
            except DigitalPassport.DoesNotExist:
                return DigitalPassport.objects.create(student_id=student.pk), True

    return _retry(operation)


def publish_passport_version(*, student_id, event_key, effective_at=None):
    """Publish or reuse an immutable snapshot for one logical update event."""

    student_uuid = UUID(str(student_id))
    event_key = _event_key(event_key)
    effective_at = effective_at or datetime.now(timezone.utc)
    if effective_at.tzinfo is None:
        raise ValidationError({"effective_at": "Must be timezone-aware."})

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
            passport, _ = DigitalPassport.objects.get_or_create(student_id=student.pk)
            passport = (
                DigitalPassport.objects.select_for_update(of=("self",))
                .select_related("latest_version")
                .get(pk=passport.pk)
            )

            prior_event = (
                PassportUpdateEvent.objects.select_related("version")
                .filter(passport=passport, event_key=event_key)
                .first()
            )
            if prior_event:
                return prior_event.version, False

            credentials = _current_credential_rows(student.pk, effective_at)
            student_snapshot = _student_snapshot(student)
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
            passport.save(update_fields=["latest_version", "updated_at"])
            PassportUpdateEvent.objects.create(
                passport=passport,
                version=version,
                event_key=event_key,
                content_sha256=content_sha256,
            )
            return version, True

    return _retry(operation)


def publish_passport_for_credential_event(*, lifecycle_event_id):
    """Integration hook called after a credential lifecycle transaction commits."""

    event = CredentialLifecycleEvent.objects.select_related("credential").get(
        pk=UUID(str(lifecycle_event_id))
    )
    return publish_passport_version(
        student_id=event.credential.student_id,
        event_key=f"credential-lifecycle:{event.pk}",
        effective_at=event.occurred_at,
    )


def schedule_passport_update_for_credential_event(*, lifecycle_event_id):
    """Schedule the integration hook without doing work inside the caller's transaction."""

    event_id = UUID(str(lifecycle_event_id))
    transaction.on_commit(
        lambda: publish_passport_for_credential_event(lifecycle_event_id=event_id)
    )
