"""Durable, PostgreSQL-coordinated Passport refresh processing."""

import logging
import random
import re
import time
import uuid
from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import DatabaseError, connection, transaction
from django.db.models import F, Max, Q
from django.utils import timezone

from .models import Credential, CredentialPassportRefresh

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 100
MAX_BATCH_SIZE = 500
DEFAULT_LEASE_SECONDS = 120
MAX_LEASE_SECONDS = 3600
DEFAULT_MAX_ATTEMPTS = 8


def _retryable(exc):
    cause = exc.__cause__ or exc
    code = getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)
    return code in {"40001", "40P01"}


def _retry_database(operation):
    if connection.in_atomic_block:
        return operation()
    for attempt in range(3):
        try:
            return operation()
        except DatabaseError as exc:
            if not _retryable(exc) or attempt == 2:
                raise
            time.sleep(random.uniform(0.005, 0.025) * (attempt + 1))


def _positive_int(name, value, maximum):
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValidationError({name: "Must be a positive integer."}) from None
    if value < 1 or value > maximum:
        raise ValidationError({name: f"Must be between 1 and {maximum}."})
    return value


def _batch_size(value):
    return _positive_int("batch_size", value, MAX_BATCH_SIZE)


def _lease_seconds(value=None):
    if value is None:
        value = getattr(settings, "PASSPORT_REFRESH_LEASE_SECONDS", DEFAULT_LEASE_SECONDS)
    return _positive_int("lease_seconds", value, MAX_LEASE_SECONDS)


def _safe_error(exc):
    message = " ".join(str(exc).split())
    message = re.sub(r"(?i)postgres(?:ql)?://\S+", "[database URL redacted]", message)
    message = re.sub(
        r"(?i)(password|secret|token|api[_-]?key|authorization)=\S+",
        r"\1=[redacted]",
        message,
    )
    return message[:1000] or type(exc).__name__


def _claim_batch_atomic(*, limit, lease_seconds, now):
    if not connection.features.has_select_for_update_skip_locked:
        raise ImproperlyConfigured(
            "Passport refresh processing requires PostgreSQL SKIP LOCKED support."
        )

    claimed = []
    terminalized = 0
    with transaction.atomic():
        rows = list(
            CredentialPassportRefresh.objects.select_for_update(skip_locked=True)
            .filter(
                Q(
                    status=CredentialPassportRefresh.Status.PENDING,
                    available_at__lte=now,
                )
                | Q(
                    status=CredentialPassportRefresh.Status.PROCESSING,
                    lease_expires_at__lte=now,
                )
            )
            .order_by("available_at", "created_at", "pk")[:limit]
        )
        for row in rows:
            if row.attempt_count >= row.max_attempts:
                row.status = CredentialPassportRefresh.Status.FAILED
                row.lease_token = None
                row.lease_expires_at = None
                row.last_error_code = "LeaseExpiredAtRetryLimit"
                row.last_error_message = "The final processing lease expired before completion."
                row.save(
                    update_fields=[
                        "status",
                        "lease_token",
                        "lease_expires_at",
                        "last_error_code",
                        "last_error_message",
                        "updated_at",
                    ]
                )
                terminalized += 1
                continue

            token = uuid.uuid4()
            row.status = CredentialPassportRefresh.Status.PROCESSING
            row.lease_token = token
            row.lease_expires_at = now + timedelta(seconds=lease_seconds)
            row.attempt_count += 1
            row.save(
                update_fields=[
                    "status",
                    "lease_token",
                    "lease_expires_at",
                    "attempt_count",
                    "updated_at",
                ]
            )
            claimed.append((row.pk, token))
    return claimed, terminalized


def _claim_one_atomic(*, refresh_id, lease_seconds, now):
    if not connection.features.has_select_for_update_skip_locked:
        raise ImproperlyConfigured(
            "Passport refresh processing requires PostgreSQL row locking."
        )
    with transaction.atomic():
        row = (
            CredentialPassportRefresh.objects.select_for_update()
            .filter(pk=refresh_id)
            .first()
        )
        if row is None:
            return None, "missing"
        if row.status in (
            CredentialPassportRefresh.Status.COMPLETED,
            CredentialPassportRefresh.Status.FAILED,
        ):
            return None, row.status.lower()
        if row.status == CredentialPassportRefresh.Status.PROCESSING:
            if row.lease_expires_at and row.lease_expires_at > now:
                return None, "processing"
        elif row.available_at > now:
            return None, "pending"

        if row.attempt_count >= row.max_attempts:
            row.status = CredentialPassportRefresh.Status.FAILED
            row.lease_token = None
            row.lease_expires_at = None
            row.last_error_code = "LeaseExpiredAtRetryLimit"
            row.last_error_message = "The final processing lease expired before completion."
            row.save(
                update_fields=[
                    "status",
                    "lease_token",
                    "lease_expires_at",
                    "last_error_code",
                    "last_error_message",
                    "updated_at",
                ]
            )
            return None, "failed"

        token = uuid.uuid4()
        row.status = CredentialPassportRefresh.Status.PROCESSING
        row.lease_token = token
        row.lease_expires_at = now + timedelta(seconds=lease_seconds)
        row.attempt_count += 1
        row.save(
            update_fields=[
                "status",
                "lease_token",
                "lease_expires_at",
                "attempt_count",
                "updated_at",
            ]
        )
        return (row.pk, token), "claimed"


def _publish_refresh(refresh_id):
    refresh = CredentialPassportRefresh.objects.only(
        "id",
        "event_key",
        "source_type",
        "student_id",
        "lifecycle_event_id",
        "source_occurred_at",
    ).get(pk=refresh_id)
    if refresh.source_type == CredentialPassportRefresh.SourceType.CREDENTIAL_LIFECYCLE:
        from apps.passports.services import publish_passport_for_credential_event

        publish_passport_for_credential_event(
            lifecycle_event_id=refresh.lifecycle_event_id
        )
        return

    from apps.passports.services import publish_passport_version

    publish_passport_version(
        student_id=refresh.student_id,
        event_key=refresh.event_key,
        effective_at=timezone.now(),
        source_occurred_at=refresh.source_occurred_at,
    )


def _finish_atomic(*, refresh_id, token):
    with transaction.atomic():
        return bool(
            CredentialPassportRefresh.objects.filter(
                pk=refresh_id,
                status=CredentialPassportRefresh.Status.PROCESSING,
                lease_token=token,
            ).update(
                status=CredentialPassportRefresh.Status.COMPLETED,
                completed_at=timezone.now(),
                lease_token=None,
                lease_expires_at=None,
                last_error_code="",
                last_error_message="",
                updated_at=timezone.now(),
            )
        )


def _retry_delay(attempt_count):
    base = max(
        0.1,
        float(getattr(settings, "PASSPORT_REFRESH_RETRY_BASE_SECONDS", 5)),
    )
    return min(3600.0, base * (2 ** max(0, attempt_count - 1))) * random.uniform(0.8, 1.2)


def _fail_atomic(*, refresh_id, token, exc):
    with transaction.atomic():
        row = (
            CredentialPassportRefresh.objects.select_for_update()
            .filter(
                pk=refresh_id,
                status=CredentialPassportRefresh.Status.PROCESSING,
                lease_token=token,
            )
            .first()
        )
        if row is None:
            return None

        row.last_error_code = type(exc).__name__[:100]
        row.last_error_message = _safe_error(exc)
        row.lease_token = None
        row.lease_expires_at = None
        if row.attempt_count >= row.max_attempts:
            row.status = CredentialPassportRefresh.Status.FAILED
        else:
            row.status = CredentialPassportRefresh.Status.PENDING
            row.available_at = timezone.now() + timedelta(
                seconds=_retry_delay(row.attempt_count)
            )
        row.save(
            update_fields=[
                "status",
                "lease_token",
                "lease_expires_at",
                "available_at",
                "last_error_code",
                "last_error_message",
                "updated_at",
            ]
        )
        return row.status


def _run_claim(refresh_id, token):
    try:
        _publish_refresh(refresh_id)
    except Exception as exc:
        status = _retry_database(
            lambda: _fail_atomic(refresh_id=refresh_id, token=token, exc=exc)
        )
        logger.warning(
            "Passport refresh %s failed (%s); persisted state=%s",
            refresh_id,
            type(exc).__name__,
            status or "lease-lost",
        )
        return status or "lease-lost"
    completed = _retry_database(
        lambda: _finish_atomic(refresh_id=refresh_id, token=token)
    )
    return "completed" if completed else "lease-lost"


def process_passport_refresh_event(*, refresh_id, lease_seconds=None):
    """Attempt one outbox row; duplicate and concurrent deliveries are safe."""

    lease_seconds = _lease_seconds(lease_seconds)
    refresh_uuid = UUID(str(refresh_id))
    claim, state = _retry_database(
        lambda: _claim_one_atomic(
            refresh_id=refresh_uuid,
            lease_seconds=lease_seconds,
            now=timezone.now(),
        )
    )
    if claim is None:
        return state
    return _run_claim(*claim)


def process_pending_passport_refreshes(*, batch_size=DEFAULT_BATCH_SIZE, lease_seconds=None):
    """Claim a bounded batch with SKIP LOCKED, then publish outside claim locks."""

    batch_size = _batch_size(batch_size)
    lease_seconds = _lease_seconds(lease_seconds)
    claims, terminalized = _retry_database(
        lambda: _claim_batch_atomic(
            limit=batch_size,
            lease_seconds=lease_seconds,
            now=timezone.now(),
        )
    )
    result = {
        "claimed": len(claims),
        "completed": 0,
        "retried": 0,
        "failed": terminalized,
        "lease_lost": 0,
    }
    for refresh_id, token in claims:
        state = _run_claim(refresh_id, token)
        if state == "completed":
            result["completed"] += 1
        elif state == CredentialPassportRefresh.Status.PENDING:
            result["retried"] += 1
        elif state in ("failed", CredentialPassportRefresh.Status.FAILED):
            result["failed"] += 1
        else:
            result["lease_lost"] += 1
    return result


def retry_failed_passport_refreshes(*, limit=DEFAULT_BATCH_SIZE):
    """Explicitly requeue a bounded set of terminal failures for operator retry."""

    limit = _batch_size(limit)

    def operation():
        with transaction.atomic():
            rows = list(
                CredentialPassportRefresh.objects.select_for_update(skip_locked=True)
                .filter(status=CredentialPassportRefresh.Status.FAILED)
                .order_by("created_at", "pk")[:limit]
            )
            for row in rows:
                row.status = CredentialPassportRefresh.Status.PENDING
                row.attempt_count = 0
                row.available_at = timezone.now()
                row.lease_token = None
                row.lease_expires_at = None
                row.completed_at = None
                row.save(
                    update_fields=[
                        "status",
                        "attempt_count",
                        "available_at",
                        "lease_token",
                        "lease_expires_at",
                        "completed_at",
                        "updated_at",
                    ]
                )
            return len(rows)

    return _retry_database(operation)


def enqueue_expired_passport_refreshes(*, limit=DEFAULT_BATCH_SIZE, now=None):
    """Queue refreshes only for students whose latest snapshot contains expired credentials."""

    limit = _batch_size(limit)
    now = now or timezone.now()
    if now.tzinfo is None:
        raise ValidationError({"now": "Must be timezone-aware."})

    stale_students = list(
        Credential.objects.filter(
            status=Credential.Status.ISSUED,
            expires_at__isnull=False,
            expires_at__lte=now,
            passport_snapshots__version__passport__latest_version_id=F(
                "passport_snapshots__version_id"
            ),
        )
        .values("student_id")
        .annotate(last_expired_at=Max("expires_at"))
        .order_by("student_id")[:limit]
    )
    if not stale_students:
        return 0

    max_attempts = _positive_int(
        "PASSPORT_REFRESH_MAX_ATTEMPTS",
        getattr(settings, "PASSPORT_REFRESH_MAX_ATTEMPTS", DEFAULT_MAX_ATTEMPTS),
        50,
    )
    rows = []
    for stale in stale_students:
        student_id = stale["student_id"]
        expired_at = stale["last_expired_at"]
        boundary = int(expired_at.timestamp() * 1_000_000)
        rows.append(
            CredentialPassportRefresh(
                event_key=f"credential-expiration:{student_id}:{boundary}",
                source_type=CredentialPassportRefresh.SourceType.EXPIRATION,
                student_id=student_id,
                source_occurred_at=expired_at,
                max_attempts=max_attempts,
            )
        )

    def operation():
        with transaction.atomic():
            table = connection.ops.quote_name(CredentialPassportRefresh._meta.db_table)
            columns = (
                "id",
                "event_key",
                "source_type",
                "student_id",
                "lifecycle_event_id",
                "source_occurred_at",
                "status",
                "available_at",
                "lease_token",
                "lease_expires_at",
                "attempt_count",
                "max_attempts",
                "completed_at",
                "last_error_code",
                "last_error_message",
                "created_at",
                "updated_at",
            )
            quoted_columns = ", ".join(connection.ops.quote_name(name) for name in columns)
            values_sql = ", ".join(
                "(" + ", ".join(["%s"] * len(columns)) + ")" for _ in rows
            )
            now = timezone.now()
            parameters = []
            for row in rows:
                parameters.extend(
                    [
                        row.pk,
                        row.event_key,
                        row.source_type,
                        row.student_id,
                        None,
                        row.source_occurred_at,
                        CredentialPassportRefresh.Status.PENDING,
                        now,
                        None,
                        None,
                        0,
                        row.max_attempts,
                        None,
                        "",
                        "",
                        now,
                        now,
                    ]
                )
            sql = (
                f"INSERT INTO {table} ({quoted_columns}) VALUES {values_sql} "
                "ON CONFLICT (event_key) DO NOTHING RETURNING id"
            )
            with connection.cursor() as cursor:
                cursor.execute(sql, parameters)
                inserted = len(cursor.fetchall())
        return inserted

    return _retry_database(operation)
