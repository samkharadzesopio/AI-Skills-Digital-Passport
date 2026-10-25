import hashlib
import json
import random
import time
import uuid
from datetime import timedelta
from pathlib import PurePosixPath
from uuid import UUID

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import DatabaseError, connection, transaction
from django.db.models import Max, Prefetch
from django.utils import timezone

from passport_pdf_renderer import (
    RENDERER_VERSION,
    render_passport_pdf,
    renderer_fingerprint,
)

from .models import (
    PassportDocument,
    PassportVersion,
    PassportVersionCredential,
    PassportVersionCredentialSkill,
    PassportVersionSkill,
)


DEFAULT_LEASE_SECONDS = 120
DEFAULT_WAIT_SECONDS = 10
DEFAULT_MAX_SKILLS = 100
DEFAULT_MAX_CREDENTIALS = 100
DEFAULT_MAX_BYTES = 5 * 1024 * 1024
RETRY_ATTEMPTS = 3


class DocumentGenerationInProgress(Exception):
    pass


class DocumentGenerationInTransaction(Exception):
    pass


def _retryable(exc):
    cause = exc.__cause__ or exc
    code = getattr(cause, "sqlstate", None) or getattr(cause, "pgcode", None)
    return code in {"40001", "40P01"}


def _retry_database(operation):
    """Retry only a short, database-only operation after transient PG errors."""

    if connection.in_atomic_block:
        return operation()
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return operation()
        except DatabaseError as exc:
            if not _retryable(exc) or attempt == RETRY_ATTEMPTS - 1:
                raise
            time.sleep(random.uniform(0.005, 0.025) * (attempt + 1))


def _request_sha256(version):
    value = json.dumps(
        {
            "passport_version": str(version.pk),
            "snapshot_sha256": version.content_sha256,
            "renderer_sha256": renderer_fingerprint(),
            "renderer_version": RENDERER_VERSION,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _attempt_key(document, token):
    return (
        f"passports/{document.passport_version.passport.public_reference}/"
        f"{document.passport_version.public_reference}/{document.public_reference}/"
        f"{token}.pdf"
    )


def _validate_storage_key(document, key):
    if not key or "\\" in key:
        raise ValidationError("Invalid passport document storage key.")
    path = PurePosixPath(key)
    expected = (
        "passports",
        str(document.passport_version.passport.public_reference),
        str(document.passport_version.public_reference),
        str(document.public_reference),
    )
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 5:
        raise ValidationError("Invalid passport document storage key.")
    if path.parts[:4] != expected or path.suffix.lower() != ".pdf":
        raise ValidationError("Invalid passport document storage key.")
    UUID(path.stem)
    return key


def _version_queryset():
    links = PassportVersionCredentialSkill.objects.select_related(
        "skill_snapshot"
    ).order_by("skill_snapshot__skill_code")
    credentials = PassportVersionCredential.objects.prefetch_related(
        Prefetch("skill_links", queryset=links)
    ).order_by("credential_public_reference")
    return PassportVersion.objects.select_related("passport").prefetch_related(
        Prefetch("credential_snapshots", queryset=credentials),
        Prefetch("skill_snapshots", queryset=PassportVersionSkill.objects.order_by("skill_code")),
    )


def _render_context(version):
    max_skills = int(getattr(settings, "PASSPORT_PDF_MAX_SKILLS", DEFAULT_MAX_SKILLS))
    max_credentials = int(
        getattr(settings, "PASSPORT_PDF_MAX_CREDENTIALS", DEFAULT_MAX_CREDENTIALS)
    )
    credentials = list(version.credential_snapshots.all())
    skills = list(version.skill_snapshots.all())
    if len(skills) > max_skills or len(credentials) > max_credentials:
        raise ValidationError(
            "Passport version exceeds the configured PDF rendering limits."
        )

    skill_sources = {skill.pk: [] for skill in skills}
    credential_rows = []
    for credential in credentials:
        credential_rows.append(
            {
                "public_reference": str(credential.credential_public_reference),
                "issuer_reference": credential.issuer_reference,
                "issuer_name": credential.issuer_name,
                "issued_date": credential.credential_issued_at.date().isoformat(),
                "expires_date": (
                    credential.credential_expires_at.date().isoformat()
                    if credential.credential_expires_at
                    else ""
                ),
            }
        )
        for link in credential.skill_links.all():
            skill_sources[link.skill_snapshot_id].append(credential)

    skill_rows = []
    for skill in skills:
        sources = skill_sources[skill.pk]
        issuers = sorted({source.issuer_name for source in sources})
        dates = sorted(source.credential_issued_at.date().isoformat() for source in sources)
        skill_rows.append(
            {
                "name": skill.skill_name,
                "category": skill.category,
                "level": skill.get_stamp_type_display()
                if hasattr(skill, "get_stamp_type_display")
                else skill.stamp_type.title(),
                "stamp_type": skill.stamp_type,
                "description": skill.description,
                "earned_through": ", ".join(issuers),
                "date_earned": dates[0] if dates else "",
            }
        )

    student = version.student_snapshot
    return {
        "student": {
            "first_name": student.get("first_name", ""),
            "last_name": student.get("last_name", ""),
            "external_student_id": student.get("external_student_id", ""),
            "program": student.get("program", ""),
            "education_level": student.get("education_level", ""),
        },
        "passport": {"public_reference": str(version.passport.public_reference)},
        "version": {
            "public_reference": str(version.public_reference),
            "number": version.version_number,
            "issued_date": version.issued_at.date().isoformat(),
        },
        "verification_reference": f"passport-version:{version.public_reference}",
        "credentials": credential_rows,
        "skills": skill_rows,
    }


def _claim_document(version_id, request_sha256, now):
    lease_seconds = int(
        getattr(settings, "PASSPORT_PDF_LEASE_SECONDS", DEFAULT_LEASE_SECONDS)
    )
    if lease_seconds < 1:
        raise ValidationError("PASSPORT_PDF_LEASE_SECONDS must be positive.")
    with transaction.atomic():
        version = (
            PassportVersion.objects.select_for_update()
            .select_related("passport")
            .get(pk=version_id)
        )
        if version.status != PassportVersion.Status.ISSUED:
            raise ValidationError("PDFs can only be generated for issued passport versions.")
        document = (
            PassportDocument.objects.select_for_update()
            .select_related("passport_version__passport")
            .filter(passport_version=version, request_sha256=request_sha256)
            .first()
        )
        if document is None:
            next_number = (
                PassportDocument.objects.filter(passport_version=version).aggregate(
                    maximum=Max("generation_number")
                )["maximum"]
                or 0
            ) + 1
            document = PassportDocument.objects.create(
                passport_version=version,
                generation_number=next_number,
                renderer_version=RENDERER_VERSION,
                request_sha256=request_sha256,
            )
        if document.status == PassportDocument.Status.ISSUED:
            return document, None, None
        if (
            document.status == PassportDocument.Status.GENERATING
            and document.lease_expires_at > now
        ):
            return document, None, None

        stale_key = document.attempt_storage_key
        token = uuid.uuid4()
        document.status = PassportDocument.Status.GENERATING
        document.lease_token = token
        document.lease_expires_at = now + timedelta(seconds=lease_seconds)
        document.attempt_count += 1
        document.attempt_storage_key = _attempt_key(document, token)
        document.storage_key = ""
        document.pdf_sha256 = ""
        document.byte_size = None
        document.generated_at = None
        document.error_code = ""
        document.error_message = ""
        document.save(
            update_fields=[
                "status", "lease_token", "lease_expires_at", "attempt_count",
                "attempt_storage_key", "storage_key", "pdf_sha256", "byte_size",
                "generated_at", "error_code", "error_message", "updated_at",
            ]
        )
        return document, token, stale_key


def _mark_failed(document_id, token, exc):
    message = " ".join(str(exc).split())[:1000] or "Document generation failed."
    with transaction.atomic():
        document = PassportDocument.objects.select_for_update().get(pk=document_id)
        if (
            document.status != PassportDocument.Status.GENERATING
            or document.lease_token != token
        ):
            return
        document.status = PassportDocument.Status.FAILED
        document.lease_token = None
        document.lease_expires_at = None
        document.error_code = type(exc).__name__[:100]
        document.error_message = message
        document.save(
            update_fields=[
                "status", "lease_token", "lease_expires_at", "error_code",
                "error_message", "updated_at",
            ]
        )


def _finalize(document_id, token, storage_key, pdf_sha256, byte_size):
    with transaction.atomic():
        document = (
            PassportDocument.objects.select_for_update()
            .select_related("passport_version__passport")
            .get(pk=document_id)
        )
        _validate_storage_key(document, storage_key)
        if document.status == PassportDocument.Status.ISSUED:
            if (
                document.storage_key == storage_key
                and document.pdf_sha256 == pdf_sha256
                and document.byte_size == byte_size
            ):
                return document
            raise ValidationError("Issued passport document metadata does not match.")
        if (
            document.status != PassportDocument.Status.GENERATING
            or document.lease_token != token
        ):
            raise DocumentGenerationInProgress("The document generation lease changed.")
        document.status = PassportDocument.Status.ISSUED
        document.storage_key = storage_key
        document.pdf_sha256 = pdf_sha256
        document.byte_size = byte_size
        document.generated_at = timezone.now()
        document.lease_token = None
        document.lease_expires_at = None
        document.save(
            update_fields=[
                "status", "storage_key", "pdf_sha256", "byte_size", "generated_at",
                "lease_token", "lease_expires_at", "updated_at",
            ]
        )
        return document


def generate_passport_document(*, passport_version_id, storage=None, renderer=None):
    """Generate, store, and issue one idempotent PDF document."""

    if connection.in_atomic_block or not connection.get_autocommit():
        raise DocumentGenerationInTransaction(
            "Passport PDF generation must run after the caller's transaction commits."
        )
    version_id = UUID(str(passport_version_id))
    storage = storage or default_storage
    renderer = renderer or render_passport_pdf
    version = PassportVersion.objects.only("id", "content_sha256").get(pk=version_id)
    request_sha256 = _request_sha256(version)
    wait_seconds = float(
        getattr(settings, "PASSPORT_PDF_WAIT_SECONDS", DEFAULT_WAIT_SECONDS)
    )
    deadline = time.monotonic() + max(0, wait_seconds)

    while True:
        document, token, stale_key = _retry_database(
            lambda: _claim_document(version_id, request_sha256, timezone.now())
        )
        if document.status == PassportDocument.Status.ISSUED:
            return document
        if token is not None:
            break
        if time.monotonic() >= deadline:
            raise DocumentGenerationInProgress("Passport PDF generation is in progress.")
        time.sleep(0.05)

    attempt_key = _validate_storage_key(document, document.attempt_storage_key)
    try:
        if stale_key and stale_key != attempt_key:
            try:
                _validate_storage_key(document, stale_key)
                storage.delete(stale_key)
            except (ValidationError, OSError):
                pass
        full_version = _version_queryset().get(pk=version_id)
        context = _render_context(full_version)
        pdf_bytes = renderer(context)
        if not isinstance(pdf_bytes, bytes) or not pdf_bytes.startswith(b"%PDF-"):
            raise ValidationError("The renderer did not return valid PDF bytes.")
        max_bytes = int(
            getattr(settings, "PASSPORT_PDF_MAX_BYTES", DEFAULT_MAX_BYTES)
        )
        if max_bytes < 1:
            raise ValidationError("PASSPORT_PDF_MAX_BYTES must be positive.")
        if len(pdf_bytes) > max_bytes:
            raise ValidationError(
                "The generated passport PDF exceeds the configured size limit."
            )
        pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        saved_key = storage.save(attempt_key, ContentFile(pdf_bytes))
        if saved_key != attempt_key:
            storage.delete(saved_key)
            raise ValidationError("Storage changed the protected document key.")
        try:
            return _retry_database(
                lambda: _finalize(
                    document.pk, token, saved_key, pdf_sha256, len(pdf_bytes)
                )
            )
        except Exception:
            storage.delete(saved_key)
            raise
    except Exception as exc:
        try:
            storage.delete(attempt_key)
        finally:
            _retry_database(lambda: _mark_failed(document.pk, token, exc))
        raise


def open_passport_document_for_student(*, document_reference, student_id, storage=None):
    """Open an issued private document only for its owning student."""

    document = (
        PassportDocument.objects.select_related("passport_version__passport")
        .filter(
            public_reference=UUID(str(document_reference)),
            status=PassportDocument.Status.ISSUED,
        )
        .first()
    )
    if document is None:
        raise PassportDocument.DoesNotExist
    if document.passport_version.passport.student_id != UUID(str(student_id)):
        raise PermissionDenied("This passport document belongs to another student.")
    key = _validate_storage_key(document, document.storage_key)
    return document, (storage or default_storage).open(key, "rb")


def find_issued_document_by_bytes(pdf_bytes):
    """Hash bytes and return matching issued metadata without exposing the file."""

    if not isinstance(pdf_bytes, bytes):
        raise ValidationError("PDF content must be bytes.")
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    return (
        PassportDocument.objects.select_related("passport_version__passport")
        .filter(pdf_sha256=digest, status=PassportDocument.Status.ISSUED)
        .first()
    )
