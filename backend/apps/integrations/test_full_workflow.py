import hashlib
import tempfile
from copy import deepcopy
from unittest.mock import Mock

from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase, override_settings

from apps.credentials.models import (
    Credential,
    CredentialLifecycleEvent,
    CredentialPassportRefresh,
)
from apps.credentials.passport_refresh import process_pending_passport_refreshes
from apps.credentials.test_support import create_test_issuer
from apps.passports.document_repository import PassportDocumentRepository
from apps.passports.document_services import generate_passport_document
from apps.passports.models import DigitalPassport, PassportDocument, PassportVersion
from apps.skills.models import Skill, VerifiedAchievement
from apps.students.models import Student
from apps.verification.document_service import DocumentVerificationService
from apps.verification.services import CredentialVerificationService

from .classroom_automation import ClassroomCredentialAutomation
from .models import ClassroomSyncEvent


COMPLETION = {
    "event_id": "INTEGRATED-COURSE-COMPLETION-001",
    "student_id": "INTEGRATED-STUDENT-001",
    "course_id": "AI-101",
    "course_name": "Introduction to Artificial Intelligence",
    "completion_status": "completed",
    "passed": True,
    "grade": 92,
    "completion_date": "2026-10-01",
}


@override_settings(
    BTU_CLASSROOM_ISSUER_REFERENCE="BTU-UNIVERSITY",
    VERIFICATION_TRUSTED_ISSUER_REFERENCES=["BTU-UNIVERSITY"],
)
class IntegratedCredentialPassportWorkflowTests(TransactionTestCase):
    def setUp(self):
        self.storage_dir = tempfile.TemporaryDirectory(prefix="integration-passport-")
        self.storage = FileSystemStorage(location=self.storage_dir.name)
        self.student = Student.objects.create(
            external_student_id=COMPLETION["student_id"],
            first_name="Synthetic",
            last_name="Workflow",
            email="workflow@example.org",
            program="AI",
            education_level="Bachelor",
            student_status="Active",
        )
        create_test_issuer("Business and Technology University")
        for code in ["AI_LITERACY", "AI_FUNDAMENTALS"]:
            Skill.objects.create(
                skill_code=code,
                skill_name=code.replace("_", " ").title(),
                category="Artificial Intelligence",
                description="Synthetic integration test skill.",
                stamp_type="FOCUSED",
                badge_asset_id="synthetic.svg",
            )
        classroom = Mock()
        classroom.get_completions.return_value = [deepcopy(COMPLETION)]
        self.automation = ClassroomCredentialAutomation(classroom)

    def tearDown(self):
        self.storage_dir.cleanup()
        super().tearDown()

    def test_completion_issues_credential_refreshes_passport_and_verifies_pdf(self):
        result = self.automation.synchronize(dry_run=False)
        self.assertEqual((result["issued"], result["failed"]), (1, 0))

        event = ClassroomSyncEvent.objects.get()
        credential = Credential.objects.get()
        self.assertEqual(event.credential_id, credential.pk)
        self.assertEqual(credential.issuer_reference, "BTU-UNIVERSITY")
        self.assertEqual(CredentialLifecycleEvent.objects.filter(credential=credential).count(), 1)
        self.assertEqual(VerifiedAchievement.objects.filter(student=self.student).count(), 2)
        self.assertEqual(
            CredentialPassportRefresh.objects.filter(
                lifecycle_event__credential=credential
            ).count(),
            1,
        )

        refresh = process_pending_passport_refreshes(batch_size=10)
        self.assertEqual(refresh["completed"], 1)
        passport = DigitalPassport.objects.get(student=self.student)
        version = passport.latest_version
        self.assertEqual(version.status, PassportVersion.Status.ISSUED)
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.credential_snapshots.count(), 1)
        self.assertEqual(
            set(version.skill_snapshots.values_list("skill_code", flat=True)),
            {"AI_LITERACY", "AI_FUNDAMENTALS"},
        )

        document = generate_passport_document(
            passport_version_id=version.pk,
            storage=self.storage,
        )
        replayed_document = generate_passport_document(
            passport_version_id=version.pk,
            storage=self.storage,
        )
        self.assertEqual(document.pk, replayed_document.pk)
        self.assertEqual(PassportDocument.objects.count(), 1)
        with self.storage.open(document.storage_key, "rb") as stored:
            pdf_bytes = stored.read()
        self.assertEqual(document.pdf_sha256, hashlib.sha256(pdf_bytes).hexdigest())

        pdf_result = DocumentVerificationService(
            repository=PassportDocumentRepository()
        ).verify(SimpleUploadedFile("passport.pdf", pdf_bytes, content_type="application/pdf"))
        self.assertEqual(pdf_result["status"], "VALID")
        self.assertTrue(pdf_result["authentic"])
        self.assertTrue(pdf_result["is_latest"])

        credential_result = CredentialVerificationService().verify(
            str(credential.public_reference)
        )
        self.assertEqual(credential_result["status"], "VALID")
        self.assertEqual(credential_result["source"], "POSTGRESQL_CREDENTIAL_REGISTRY")

        replay = self.automation.synchronize(dry_run=False)
        self.assertEqual((replay["issued"], replay["skipped"]), (0, 1))
        self.assertEqual(Credential.objects.count(), 1)
        self.assertEqual(PassportVersion.objects.count(), 1)
        self.assertEqual(PassportDocument.objects.count(), 1)
        self.assertEqual(process_pending_passport_refreshes(batch_size=10)["claimed"], 0)
