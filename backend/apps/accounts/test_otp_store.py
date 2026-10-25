
from datetime import timedelta

from django.test import SimpleTestCase
from django.utils import timezone

from .otp_store import OTPStore


class OTPStoreTests(SimpleTestCase):

    def setUp(self):
        self.store = OTPStore()
        self.email = "student@btu.edu.ge"

    def test_correct_code(self):
        code = self.store.issue(self.email)

        self.assertTrue(
            self.store.verify(self.email, code)
        )

    def test_code_cannot_be_reused(self):
        code = self.store.issue(self.email)

        self.assertTrue(
            self.store.verify(self.email, code)
        )

        self.assertFalse(
            self.store.verify(self.email, code)
        )

    def test_wrong_code(self):
        code = self.store.issue(self.email)

        self.assertFalse(
            self.store.verify(self.email, "invalid")
        )

        self.assertTrue(
            self.store.verify(self.email, code)
        )

    def test_expired_code(self):
        code = self.store.issue(self.email)

        self.store._codes[self.email]["expires_at"] = (
            timezone.now() - timedelta(seconds=1)
        )

        self.assertFalse(
            self.store.verify(self.email, code)
        )

    def test_attempt_limit(self):
        code = self.store.issue(self.email)

        wrong_code = (
            "000000" if code != "000000" else "999999"
        )

        for _ in range(5):
            self.assertFalse(
                self.store.verify(self.email, wrong_code)
            )

        self.assertFalse(
            self.store.verify(self.email, code)
        )
