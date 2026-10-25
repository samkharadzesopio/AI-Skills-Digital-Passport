
from unittest.mock import patch

from django.test import SimpleTestCase

from .services import (
    send_verification_email,
    verify_verification_code,
)


class OTPServiceTests(SimpleTestCase):

    @patch("apps.accounts.services.send_mail")
    def test_email_code_can_be_verified(self, mock_send):
        email = "student@btu.edu.ge"

        send_verification_email(email)

        mock_send.assert_called_once()

        message = mock_send.call_args.kwargs["message"]

        code = message.split(
            "Your verification code is: "
        )[1][:6]

        self.assertEqual(len(code), 6)

        self.assertTrue(
            verify_verification_code(email, code)
        )

        # The same code cannot be reused.
        self.assertFalse(
            verify_verification_code(email, code)
        )

    @patch("apps.accounts.services.send_mail")
    def test_wrong_code_is_rejected(self, mock_send):
        email = "other@btu.edu.ge"

        send_verification_email(email)

        message = mock_send.call_args.kwargs["message"]
        code = message.split(
            "Your verification code is: "
        )[1][:6]

        wrong_code = (
            "000000" if code != "000000"
            else "999999"
        )

        self.assertFalse(
            verify_verification_code(email, wrong_code)
        )
