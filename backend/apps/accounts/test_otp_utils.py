
from django.test import SimpleTestCase

from .otp_utils import (
    normalize_btu_email,
    generate_otp,
    hash_otp,
    verify_otp_hash,
)


class OTPUtilityTests(SimpleTestCase):

    def test_btu_email_is_accepted(self):
        result = normalize_btu_email(
            " Student@BTU.EDU.GE "
        )
        self.assertEqual(
            result, "student@btu.edu.ge"
        )

    def test_other_domains_are_rejected(self):
        with self.assertRaises(ValueError):
            normalize_btu_email(
                "student@gmail.com"
            )

    def test_code_has_six_digits(self):
        code = generate_otp()

        self.assertEqual(len(code), 6)
        self.assertTrue(code.isascii())
        self.assertTrue(code.isdigit())

    def test_correct_code_is_verified(self):
        email = "student@btu.edu.ge"
        code = "123456"

        stored_hash = hash_otp(email, code)

        self.assertTrue(
            verify_otp_hash(
                email, code, stored_hash
            )
        )

    def test_wrong_code_is_rejected(self):
        email = "student@btu.edu.ge"

        stored_hash = hash_otp(
            email, "123456"
        )

        self.assertFalse(
            verify_otp_hash(
                email, "654321", stored_hash
            )
        )
