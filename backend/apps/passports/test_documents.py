import hashlib
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import pymupdf
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import (
    DatabaseError,
    IntegrityError,
    close_old_connections,
    connection,
    transaction,
)
from django.test import TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext

from apps.credentials.test_support import create_test_issuer
from apps.credentials.services import issue_credential, revoke_credential
from apps.skills.models import AchievementSourceEvent, Skill, VerifiedAchievement
from apps.students.models import Student
from apps.verification.document_service import DocumentVerificationService

from .document_repository import PassportDocumentRepository
from .document_services import (
    DocumentGenerationInTransaction,
    _render_context,
    _retry_database,
    _validate_storage_key,
    _version_queryset,
    find_issued_document_by_bytes,
    generate_passport_document,
    open_passport_document_for_student,
)
from .models import PassportDocument
from .services import publish_passport_version


class FailingOnceStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.failed = False

    def save(self, name, content, max_length=None):
        if not self.failed:
            self.failed = True
            raise OSError("synthetic storage failure")
        return super().save(name, content, max_length=max_length)


class DocumentDataMixin:
    def setUp(self):
        super().setUp()
        self.storage_dir = tempfile.TemporaryDirectory(prefix="passport-doc-test-")
        self.storage = FileSystemStorage(location=self.storage_dir.name)
        self.now = datetime(2026, 10, 25, 12, 0, tzinfo=timezone.utc)
        self.student = Student.objects.create(
            external_student_id="PDF-STUDENT-001",
            first_name="PDF",
            last_name="Student",
            email="pdf-student@example.org",
            program="AI",
            education_level="Bachelor",
            student_status="Active",
        )
        self.issuer = create_test_issuer("BTU Synthetic University")
        self.skill = Skill.objects.create(
            skill_code="PDF-SKILL-001",
            skill_name="Machine Learning Foundations",
            category="Artificial Intelligence",
            description="Build and evaluate foundational machine learning systems.",
            stamp_type="APPLIED",
            badge_asset_id="ai_applied.png",
        )
        source = AchievementSourceEvent.objects.create(
            source="PDF_TEST",
            source_event_id="PDF-EVENT-001",
            payload_sha256="c" * 64,
        )
        achievement = VerifiedAchievement.objects.create(
            student=self.student,
            skill=self.skill,
            source_event=source,
            earned_on=date(2026, 10, 20),
            verification_status="VERIFIED",
        )
        self.credential = issue_credential(
            issuer_reference=self.issuer.reference,
            idempotency_key="PDF-CREDENTIAL-001",
            achievement_ids=[achievement.pk],
            issued_at=self.now - timedelta(days=1),
        )
        self.version, _ = publish_passport_version(
            student_id=self.student.pk,
            event_key="PDF-PASSPORT-V1",
            effective_at=self.now,
        )

    def tearDown(self):
        self.storage_dir.cleanup()
        super().tearDown()


class PassportDocumentServiceTests(DocumentDataMixin, TransactionTestCase):
    reset_sequences = True

    def test_generates_pdf_from_snapshot_and_persists_hash_metadata(self):
        document = generate_passport_document(
            passport_version_id=self.version.pk, storage=self.storage
        )
        self.assertEqual(document.status, PassportDocument.Status.ISSUED)
        self.assertEqual(document.generation_number, 1)
        self.assertTrue(self.storage.exists(document.storage_key))
        with self.storage.open(document.storage_key, "rb") as stored:
            pdf_bytes = stored.read()
        self.assertEqual(hashlib.sha256(pdf_bytes).hexdigest(), document.pdf_sha256)
        self.assertEqual(len(pdf_bytes), document.byte_size)
        pdf = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        try:
            text = "\n".join(page.get_text() for page in pdf)
        finally:
            pdf.close()
        self.assertIn("PDF", text)
        self.assertIn("Student", text)
        self.assertIn("MACHINE LEARNING FOUNDATIONS", " ".join(text.split()))
        self.assertIn(str(self.version.passport.public_reference), text)
        self.assertIn(str(self.version.public_reference), text)
        self.assertIn(str(self.credential.public_reference), text)
        self.assertIn(self.issuer.display_name, text)

    def test_repeated_generation_reuses_document_and_stored_bytes(self):
        first = generate_passport_document(
            passport_version_id=self.version.pk, storage=self.storage
        )
        second = generate_passport_document(
            passport_version_id=self.version.pk, storage=self.storage
        )
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(PassportDocument.objects.count(), 1)
        self.assertEqual(first.attempt_count, 1)

    def test_renderer_change_creates_new_generation_and_preserves_previous_file(self):
        first = generate_passport_document(
            passport_version_id=self.version.pk, storage=self.storage
        )
        with patch(
            "apps.passports.document_services.renderer_fingerprint",
            return_value="f" * 64,
        ):
            second = generate_passport_document(
                passport_version_id=self.version.pk, storage=self.storage
            )
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual((first.generation_number, second.generation_number), (1, 2))
        self.assertTrue(self.storage.exists(first.storage_key))
        self.assertTrue(self.storage.exists(second.storage_key))
        self.assertEqual(first.pdf_sha256, second.pdf_sha256)

    @override_settings(PASSPORT_PDF_MAX_BYTES=16)
    def test_oversized_render_is_rejected_before_storage(self):
        def oversized_renderer(context):
            return b"%PDF-1.7\n" + (b"x" * 32)

        with self.assertRaisesMessage(
            ValidationError, "exceeds the configured size limit"
        ):
            generate_passport_document(
                passport_version_id=self.version.pk,
                storage=self.storage,
                renderer=oversized_renderer,
            )
        document = PassportDocument.objects.get()
        self.assertEqual(document.status, PassportDocument.Status.FAILED)
        self.assertEqual(document.error_code, "ValidationError")
        self.assertFalse(any(Path(self.storage_dir.name).rglob("*.pdf")))

    def test_storage_failure_is_durable_and_same_document_can_retry(self):
        storage = FailingOnceStorage(location=self.storage_dir.name)
        with self.assertRaises(OSError):
            generate_passport_document(
                passport_version_id=self.version.pk, storage=storage
            )
        failed = PassportDocument.objects.get()
        self.assertEqual(failed.status, PassportDocument.Status.FAILED)
        self.assertEqual(failed.error_code, "OSError")
        recovered = generate_passport_document(
            passport_version_id=self.version.pk, storage=storage
        )
        self.assertEqual(recovered.pk, failed.pk)
        self.assertEqual(recovered.status, PassportDocument.Status.ISSUED)
        self.assertEqual(recovered.attempt_count, 2)

    def test_generation_is_rejected_inside_caller_transaction(self):
        with transaction.atomic(), self.assertRaises(DocumentGenerationInTransaction):
            generate_passport_document(
                passport_version_id=self.version.pk, storage=self.storage
            )
        self.assertFalse(PassportDocument.objects.exists())

    def test_private_retrieval_checks_owner_and_protected_path(self):
        document = generate_passport_document(
            passport_version_id=self.version.pk, storage=self.storage
        )
        returned, stream = open_passport_document_for_student(
            document_reference=document.public_reference,
            student_id=self.student.pk,
            storage=self.storage,
        )
        try:
            self.assertEqual(returned.pk, document.pk)
            self.assertTrue(stream.read(5).startswith(b"%PDF"))
        finally:
            stream.close()
        with self.assertRaises(PermissionDenied):
            open_passport_document_for_student(
                document_reference=document.public_reference,
                student_id="00000000-0000-0000-0000-000000000001",
                storage=self.storage,
            )
        with self.assertRaises(ValidationError):
            _validate_storage_key(document, "../../private.pdf")

    def test_hash_lookup_and_existing_verification_contract(self):
        document = generate_passport_document(
            passport_version_id=self.version.pk, storage=self.storage
        )
        with self.storage.open(document.storage_key, "rb") as stored:
            pdf_bytes = stored.read()
        self.assertEqual(find_issued_document_by_bytes(pdf_bytes).pk, document.pk)
        result = DocumentVerificationService(
            repository=PassportDocumentRepository()
        ).verify(
            SimpleUploadedFile(
                "passport.pdf", pdf_bytes, content_type="application/pdf"
            )
        )
        self.assertEqual(result["status"], "VALID")
        self.assertTrue(result["authentic"])

    def test_snapshot_loading_has_constant_query_count_for_multiple_rows(self):
        for index in range(4):
            skill = Skill.objects.create(
                skill_code=f"PDF-SKILL-{index + 2:03d}",
                skill_name=f"Synthetic PDF Skill {index + 2}",
                category="Artificial Intelligence",
                description="Synthetic description used for PDF query testing.",
                stamp_type="FOCUSED",
                badge_asset_id="ai_focused.png",
            )
            source = AchievementSourceEvent.objects.create(
                source="PDF_TEST",
                source_event_id=f"PDF-EVENT-{index + 2:03d}",
                payload_sha256=f"{index + 1:x}" * 64,
            )
            achievement = VerifiedAchievement.objects.create(
                student=self.student,
                skill=skill,
                source_event=source,
                earned_on=date(2026, 10, 20),
                verification_status="VERIFIED",
            )
            issue_credential(
                issuer_reference=self.issuer.reference,
                idempotency_key=f"PDF-CREDENTIAL-{index + 2:03d}",
                achievement_ids=[achievement.pk],
                issued_at=self.now - timedelta(hours=index + 2),
            )
        version, _ = publish_passport_version(
            student_id=self.student.pk,
            event_key="PDF-PASSPORT-MULTI-ROW",
            effective_at=self.now + timedelta(hours=1),
        )
        with CaptureQueriesContext(connection) as queries:
            context = _render_context(_version_queryset().get(pk=version.pk))
        self.assertEqual(len(queries), 4)
        self.assertEqual(len(context["credentials"]), 5)
        self.assertEqual(len(context["skills"]), 5)

    @override_settings(
        CREDENTIAL_REVOCATION_AUTHORIZER=lambda actor, credential: "operator:pdf-test"
    )
    def test_historical_pdf_survives_revocation_and_new_version_excludes_skill(self):
        first_document = generate_passport_document(
            passport_version_id=self.version.pk, storage=self.storage
        )
        revoke_credential(
            public_reference=self.credential.public_reference,
            actor=object(),
            reason="Synthetic PDF revocation",
        )
        second_version, _ = publish_passport_version(
            student_id=self.student.pk,
            event_key="PDF-PASSPORT-V2-REVOKED",
            effective_at=self.now + timedelta(hours=1),
        )
        second_document = generate_passport_document(
            passport_version_id=second_version.pk, storage=self.storage
        )
        with self.storage.open(first_document.storage_key, "rb") as stored:
            old_pdf = pymupdf.open(stream=stored.read(), filetype="pdf")
        try:
            old_text = " ".join(page.get_text() for page in old_pdf)
        finally:
            old_pdf.close()
        with self.storage.open(second_document.storage_key, "rb") as stored:
            new_pdf = pymupdf.open(stream=stored.read(), filetype="pdf")
        try:
            new_text = " ".join(page.get_text() for page in new_pdf)
        finally:
            new_pdf.close()
        self.assertIn("MACHINE LEARNING FOUNDATIONS", " ".join(old_text.split()))
        self.assertNotIn("MACHINE LEARNING FOUNDATIONS", " ".join(new_text.split()))
        old_result = DocumentVerificationService(
            repository=PassportDocumentRepository()
        ).verify(
            SimpleUploadedFile(
                "old.pdf",
                Path(self.storage.path(first_document.storage_key)).read_bytes(),
                content_type="application/pdf",
            )
        )
        self.assertEqual(old_result["status"], "REVOKED")
        self.assertTrue(old_result["authentic"])
        self.assertFalse(old_result["is_latest"])


class PassportDocumentIntegrityTests(DocumentDataMixin, TransactionTestCase):
    reset_sequences = True

    def test_issued_document_metadata_cannot_be_rewritten_or_deleted(self):
        document = generate_passport_document(
            passport_version_id=self.version.pk, storage=self.storage
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            PassportDocument.objects.filter(pk=document.pk).update(pdf_sha256="f" * 64)
        with self.assertRaises(IntegrityError), transaction.atomic():
            document.delete()

    def test_serialization_failure_gets_a_bounded_database_only_retry(self):
        class SerializationFailure(Exception):
            sqlstate = "40001"

        calls = 0

        def operation():
            nonlocal calls
            calls += 1
            if calls == 1:
                raise DatabaseError("synthetic serialization failure") from SerializationFailure()
            return "completed"

        with patch("apps.passports.document_services.time.sleep") as sleep:
            self.assertEqual(_retry_database(operation), "completed")
        self.assertEqual(calls, 2)
        sleep.assert_called_once()


class PassportDocumentConcurrencyTests(DocumentDataMixin, TransactionTestCase):
    reset_sequences = True

    def test_concurrent_generation_renders_once_and_returns_one_document(self):
        barrier = Barrier(2)
        render_count = 0
        render_lock = threading.Lock()

        from passport_pdf_renderer import render_passport_pdf

        def slow_renderer(context):
            nonlocal render_count
            with render_lock:
                render_count += 1
            time.sleep(0.25)
            return render_passport_pdf(context)

        def generate_one():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return str(
                    generate_passport_document(
                        passport_version_id=self.version.pk,
                        storage=self.storage,
                        renderer=slow_renderer,
                    ).pk
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: generate_one(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(render_count, 1)
        self.assertEqual(PassportDocument.objects.count(), 1)
