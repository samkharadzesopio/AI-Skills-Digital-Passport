from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from .models import OTPChallenge
from .otp_store import AuthRateLimitExceeded, consume_login_budget, otp_store


class OTPStoreTests(TestCase):
    def setUp(self):
        self.email = "student@btu.edu.ge"

    def test_correct_code_is_single_use_and_only_hash_is_persisted(self):
        code = otp_store.issue(self.email, ip_address="192.0.2.10")
        record = OTPChallenge.objects.get()
        self.assertNotEqual(record.code_digest, code)
        self.assertNotIn(self.email, record.email_digest)
        self.assertTrue(otp_store.verify(self.email, code))
        self.assertFalse(otp_store.verify(self.email, code))

    def test_wrong_code_increments_bounded_attempts(self):
        code = otp_store.issue(self.email, ip_address="192.0.2.11")
        wrong = "000000" if code != "000000" else "999999"
        for _ in range(5):
            self.assertFalse(otp_store.verify(self.email, wrong))
        self.assertFalse(otp_store.verify(self.email, code))
        record = OTPChallenge.objects.get()
        self.assertEqual(record.attempts, 5)
        self.assertIsNotNone(record.consumed_at)

    def test_expired_code_is_rejected_and_consumed(self):
        code = otp_store.issue(self.email, ip_address="192.0.2.12")
        OTPChallenge.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertFalse(otp_store.verify(self.email, code))
        self.assertIsNotNone(OTPChallenge.objects.get().consumed_at)

    def test_resending_invalidates_previous_code(self):
        previous = otp_store.issue(self.email, ip_address="192.0.2.13")
        current = otp_store.issue(self.email, ip_address="192.0.2.13")
        self.assertFalse(otp_store.verify(self.email, previous))
        self.assertTrue(otp_store.verify(self.email, current))
        self.assertEqual(OTPChallenge.objects.count(), 2)

    @override_settings(AUTH_OTP_EMAIL_REQUESTS_PER_WINDOW=1)
    def test_persistent_account_rate_limit(self):
        otp_store.issue(self.email, ip_address="192.0.2.14")
        with self.assertRaises(AuthRateLimitExceeded):
            otp_store.issue(self.email, ip_address="192.0.2.15")

    @override_settings(AUTH_OTP_IP_REQUESTS_PER_WINDOW=1)
    def test_persistent_ip_rate_limit_across_accounts(self):
        otp_store.issue(self.email, ip_address="192.0.2.16")
        with self.assertRaises(AuthRateLimitExceeded):
            otp_store.issue("other@btu.edu.ge", ip_address="192.0.2.16")

    @override_settings(AUTH_LOGIN_EMAIL_ATTEMPTS_PER_WINDOW=1)
    def test_login_rate_limit_is_persistent_per_account(self):
        consume_login_budget(self.email, "192.0.2.17")
        with self.assertRaises(AuthRateLimitExceeded):
            consume_login_budget(self.email, "192.0.2.18")


class OTPConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_concurrent_correct_verification_consumes_once(self):
        email = "concurrent@btu.edu.ge"
        code = otp_store.issue(email, ip_address="192.0.2.20")
        barrier = Barrier(2)

        def verify_once():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return otp_store.verify(email, code)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: verify_once(), range(2)))
        self.assertEqual(sum(results), 1)
