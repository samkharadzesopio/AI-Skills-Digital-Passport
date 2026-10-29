"""Atomic achievement persistence; deliberately independent of Classroom adapters."""

import hashlib
import json
import random
import time
from dataclasses import dataclass
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.db.models import Subquery

from apps.students.models import Student

from .achievement_limits import bounded_evidence, get_achievement_limits, validate_text
from .models import AchievementSourceEvent, Skill, VerifiedAchievement


class SourceEventConflict(Exception):
    """The event identity was replayed with different or inconsistent award data."""


@dataclass(frozen=True)
class _PreparedRequest:
    source: str
    source_event_id: str
    external_student_id: str
    codes: frozenset
    earned_on: date
    verification_status: str
    course_id: str
    evidence_reference: str
    evidence: dict


def _identifier(value, field, maximum):
    validate_text(value, field, maximum)
    if not value or value != value.strip():
        raise ValidationError({field: "Supply a nonblank canonical identifier."})


def _prepare_request(*, limits, source, source_event_id, external_student_id,
                     approved_skill_codes, earned_on, verification_status, course_id,
                     evidence_reference, evidence):
    _identifier(source, "source", 100)
    _identifier(source_event_id, "source_event_id", limits.max_event_id_length)
    _identifier(external_student_id, "external_student_id", 120)
    validate_text(course_id, "course_id", 255)
    if course_id != course_id.strip():
        raise ValidationError({"course_id": "Supply a canonical course ID or an empty string."})
    validate_text(evidence_reference, "evidence_reference", limits.max_evidence_reference_length)
    if not isinstance(earned_on, date) or isinstance(earned_on, datetime):
        raise ValidationError({"earned_on": "Expected a date, not a datetime or unparsed string."})
    if verification_status not in VerifiedAchievement.VerificationStatus.values:
        raise ValidationError({"verification_status": "Unsupported verification status."})
    if not isinstance(approved_skill_codes, (list, tuple, set, frozenset)) or not approved_skill_codes:
        raise ValidationError({"approved_skill_codes": "Supply a nonempty collection of approved skill codes."})
    if len(approved_skill_codes) > limits.max_skills_per_event:
        raise ValidationError({"approved_skill_codes": f"At most {limits.max_skills_per_event} skills are allowed per event."})
    for code in approved_skill_codes:
        _identifier(code, "approved_skill_codes", 100)
    codes = frozenset(approved_skill_codes)
    if len(codes) != len(approved_skill_codes):
        raise ValidationError({"approved_skill_codes": "Repeated skill codes are not allowed."})
    return _PreparedRequest(
        source, source_event_id, external_student_id, codes, earned_on, verification_status,
        course_id, evidence_reference, bounded_evidence(evidence, limits),
    )


def _resolve_identities(request):
    # The uncorrelated scalar subquery is one PostgreSQL initplan, not one lookup
    # per skill. Fetch UUIDs only; existing profile/catalog repositories stay intact.
    student = Student.objects.filter(external_student_id=request.external_student_id).values("id")[:1]
    rows = list(Skill.objects.filter(skill_code__in=request.codes).annotate(
        student_uuid=Subquery(student),
    ).order_by("id").values_list("id", "student_uuid"))
    if not rows:
        # Preserve Student.DoesNotExist precedence even when no skills match.
        Student.objects.values_list("id", flat=True).get(external_student_id=request.external_student_id)
    elif rows[0][1] is None:
        raise Student.DoesNotExist("Student matching the external identifier does not exist.")
    if len(rows) != len(request.codes):
        raise ValidationError({"approved_skill_codes": "Every approved skill must exist in the catalog."})
    return rows[0][1], tuple(row[0] for row in rows)


def _fingerprint(request, identities):
    student_uuid, skill_uuids = identities
    # Preserve format 1 byte-for-byte so already-persisted receipts still replay.
    payload = {
        "format": 1, "student_uuid": str(student_uuid),
        "skill_uuids": [str(pk) for pk in skill_uuids],
        "earned_on": request.earned_on.isoformat(), "verification_status": request.verification_status,
        "course_id": request.course_id, "evidence_reference": request.evidence_reference,
        "evidence": request.evidence,
    }
    return hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _record_once(request, identities, fingerprint, limits):
    with transaction.atomic():
        # Revalidate after the autocommit preparation read. A concurrent identity
        # replacement must not attach the fingerprint to a different student/skill.
        if _resolve_identities(request) != identities:
            raise ValidationError("Student or skill identities changed during preparation; resubmit the event.")
        student_uuid, skill_uuids = identities
        # One lookup/lock on existing receipts; new inserts already own their row.
        # get_or_create's savepoint handles a concurrent unique-key winner safely.
        event, created = AchievementSourceEvent.objects.select_for_update().get_or_create(
            source=request.source, source_event_id=request.source_event_id,
            defaults={
                "course_id": request.course_id, "evidence_reference": request.evidence_reference,
                "evidence": request.evidence, "payload_sha256": fingerprint,
            },
        )
        if not created:
            if (
                event.payload_sha256 != fingerprint or event.course_id != request.course_id
                or event.evidence_reference != request.evidence_reference or event.evidence != request.evidence
            ):
                raise SourceEventConflict("Source event was already recorded with different award data.")
            awards = list(event.achievements.order_by("skill_id"))
            actual = [(a.student_id, a.skill_id, a.earned_on, a.verification_status) for a in awards]
            expected = [(student_uuid, pk, request.earned_on, request.verification_status) for pk in skill_uuids]
            if actual != expected:
                raise SourceEventConflict("Stored awards no longer match the original source event batch.")
            return awards, False
        awards = VerifiedAchievement.objects.bulk_create([
            VerifiedAchievement(
                student_id=student_uuid, skill_id=pk, source_event=event,
                earned_on=request.earned_on, verification_status=request.verification_status,
            ) for pk in skill_uuids
        ], batch_size=limits.bulk_batch_size)
        return awards, True


def record_verified_achievements(
    *, source, source_event_id, external_student_id, approved_skill_codes, earned_on,
    verification_status=VerifiedAchievement.VerificationStatus.PENDING,
    course_id="", evidence_reference="", evidence=None,
):
    """Return (awards, created); trusted callers supply the approved complete batch.

    Pure validation/serialization precede all database access. UUID-bound format-1
    fingerprints are prepared outside our write transaction and identities checked
    again inside it. Outer-transaction callers own retries of their whole operation.
    """
    limits = get_achievement_limits()
    request = _prepare_request(
        limits=limits, source=source, source_event_id=source_event_id,
        external_student_id=external_student_id, approved_skill_codes=approved_skill_codes,
        earned_on=earned_on, verification_status=verification_status, course_id=course_id,
        evidence_reference=evidence_reference, evidence=evidence,
    )
    connection = transaction.get_connection()
    attempts = 1 if connection.in_atomic_block or not connection.get_autocommit() else limits.retry_attempts
    for attempt in range(attempts):
        try:
            identities = _resolve_identities(request)
            fingerprint = _fingerprint(request, identities)
            return _record_once(request, identities, fingerprint, limits)
        except DatabaseError as exc:
            cause = exc.__cause__
            sqlstate = getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)
            if sqlstate not in {"40001", "40P01"} or attempt + 1 == attempts:
                raise
            # Only entire, rolled-back transactions are retried. Never sleep while
            # holding event locks or inside a caller-owned transaction.
            delay = min(limits.retry_max_delay, limits.retry_base_delay * 2 ** attempt)
            time.sleep(delay * random.uniform(0.5, 1.0))
