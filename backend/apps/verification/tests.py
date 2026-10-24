
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
