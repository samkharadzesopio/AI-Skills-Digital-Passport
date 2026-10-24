
from datetime import datetime, timezone
from django.test import SimpleTestCase

from .services import CredentialVerificationService


class CredentialVerificationTests(SimpleTestCase):

    def setUp(self):
        self.service = CredentialVerificationService(
            clock=lambda: datetime(
                2026, 10, 24,
                tzinfo=timezone.utc
            )
        )

    def test_valid(self):
        result = self.service.verify("MOCK-CRED-001")
        self.assertEqual(result["status"], "VALID")

    def test_revoked(self):
        result = self.service.verify("MOCK-CRED-002")
        self.assertEqual(result["status"], "REVOKED")

    def test_expired(self):
        result = self.service.verify("MOCK-CRED-003")
        self.assertEqual(result["status"], "EXPIRED")

    def test_untrusted_issuer(self):
        result = self.service.verify("MOCK-CRED-004")
        self.assertEqual(result["status"], "INVALID")

    def test_unknown(self):
        result = self.service.verify("MOCK-CRED-999")
        self.assertEqual(result["status"], "NOT_FOUND")

    def test_private_data_not_exposed(self):
        result = self.service.verify("MOCK-CRED-001")
        self.assertNotIn("student_name", result)
        self.assertNotIn("email", result)
        self.assertNotIn("grade", result)


import hashlib

from django.core.files.uploadedfile import SimpleUploadedFile

from .document_service import DocumentVerificationService


class FakeDocumentRepository:
    def __init__(self, pdf_hash, version, latest, status="ISSUED"):
        self.pdf_hash = pdf_hash
        self.version = version
        self.latest = latest
        self.status = status

    def find_by_hash(self, pdf_hash):
        if pdf_hash != self.pdf_hash:
            return None

        return {
            "passport_id": "MOCK-PASSPORT-001",
            "version_number": self.version,
            "status": self.status,
        }

    def get_passport(self, passport_id):
        return {
            "passport_id": passport_id,
            "latest_version_number": self.latest,
        }


class DocumentVerificationTests(SimpleTestCase):

    def setUp(self):
        self.pdf_bytes = (
            b"%PDF-1.4\n"
            b"Simulated PDF test content\n"
            b"%%EOF\n"
        )
        self.pdf_hash = hashlib.sha256(
            self.pdf_bytes
        ).hexdigest()

    def make_pdf(self, content=None):
        return SimpleUploadedFile(
            "passport.pdf",
            self.pdf_bytes if content is None else content,
            content_type="application/pdf",
        )

    def make_service(
        self, version=1, latest=1, status="ISSUED"
    ):
        return DocumentVerificationService(
            repository=FakeDocumentRepository(
                self.pdf_hash,
                version,
                latest,
                status,
            )
        )

    def test_latest_pdf_is_valid(self):
        result = self.make_service(
            version=3, latest=3
        ).verify(self.make_pdf())

        self.assertEqual(result["status"], "VALID")
        self.assertTrue(result["authentic"])
        self.assertTrue(result["is_latest"])

    def test_older_pdf_is_outdated(self):
        result = self.make_service(
            version=1, latest=3
        ).verify(self.make_pdf())

        self.assertEqual(result["status"], "OUTDATED")
        self.assertTrue(result["authentic"])
        self.assertFalse(result["is_latest"])

    def test_revoked_pdf_is_invalid(self):
        result = self.make_service(
            status="REVOKED"
        ).verify(self.make_pdf())

        self.assertEqual(result["status"], "INVALID")
        self.assertFalse(result["authentic"])

    def test_unknown_hash_is_unverifiable(self):
        result = self.make_service().verify(
            self.make_pdf(
                b"%PDF-1.4\nChanged content\n%%EOF\n"
            )
        )

        self.assertEqual(
            result["status"], "UNVERIFIABLE"
        )

    def test_non_pdf_is_invalid(self):
        result = self.make_service().verify(
            self.make_pdf(b"This is not a PDF")
        )

        self.assertEqual(result["status"], "INVALID")

    def test_oversized_pdf_is_invalid(self):
        oversized = (
            b"%PDF-1.4\n"
            + b"A" * (5 * 1024 * 1024)
            + b"\n%%EOF"
        )

        result = self.make_service().verify(
            self.make_pdf(oversized)
        )

        self.assertEqual(result["status"], "INVALID")

    def test_inconsistent_version_is_unverifiable(self):
        result = self.make_service(
            version=4, latest=3
        ).verify(self.make_pdf())

        self.assertEqual(
            result["status"], "UNVERIFIABLE"
        )
