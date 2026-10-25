
import hmac
import threading
from datetime import timedelta

from django.utils import timezone

from .otp_utils import (
    generate_otp,
    hash_otp,
    normalize_btu_email,
)


class OTPStore:
    """
    Development-only in-memory OTP storage.

    Does not persist across server restarts or
    work across multiple server processes.
    """

    EXPIRY_MINUTES = 5
    MAX_ATTEMPTS = 5

    def __init__(self):
        self._codes = {}
        self._lock = threading.Lock()

    def issue(self, email):
        email = normalize_btu_email(email)
        code = generate_otp()

        with self._lock:
            self._codes[email] = {
                "hash": hash_otp(email, code),
                "expires_at": timezone.now()
                + timedelta(minutes=self.EXPIRY_MINUTES),
                "attempts": 0,
            }

        return code

    def verify(self, email, code):
        email = normalize_btu_email(email)

        if (
            not isinstance(code, str)
            or len(code) != 6
            or not code.isascii()
            or not code.isdigit()
        ):
            return False

        with self._lock:
            record = self._codes.get(email)

            if record is None:
                return False

            if timezone.now() >= record["expires_at"]:
                del self._codes[email]
                return False

            if record["attempts"] >= self.MAX_ATTEMPTS:
                return False

            record["attempts"] += 1

            correct = hmac.compare_digest(
                hash_otp(email, code),
                record["hash"],
            )

            if correct:
                del self._codes[email]

            return correct
