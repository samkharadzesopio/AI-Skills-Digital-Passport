from unittest.mock import patch

from django.test import TestCase

from .models import OTPChallenge, User
from .services import EmailDeliveryUnavailable, send_verification_email, verify_verification_code


class OTPServiceTests(TestCase):
    def setUp(self):
        self.email = "student@btu.edu.ge"
        self.user = User.objects.create_user(
            email=self.email,
            password="Str0ng-Passphrase!2026",
            is_email_verified=False,
        )

    @patch("apps.accounts.services.send_mail", return_value=1)
    def test_email_code_can_be_verified_once(self, mock_send):
        send_verification_email(self.email)
        message = mock_send.call_args.kwargs["message"]
        code = message.split("Your verification code is ")[1][:6]

        self.assertEqual(len(code), 6)
        self.assertTrue(verify_verification_code(self.email, code))
        self.assertFalse(verify_verification_code(self.email, code))
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_email_verified)

    @patch("apps.accounts.services.send_mail", return_value=1)
    def test_wrong_email_code_is_rejected(self, mock_send):
        send_verification_email(self.email)
        message = mock_send.call_args.kwargs["message"]
        code = message.split("Your verification code is ")[1][:6]
        wrong = "000000" if code != "000000" else "999999"
        self.assertFalse(verify_verification_code(self.email, wrong))

    @patch("apps.accounts.services.send_mail", return_value=1)
    def test_verified_email_does_not_receive_another_code(self, mock_send):
        self.user.is_email_verified = True
        self.user.save(update_fields=["is_email_verified"])
        send_verification_email(self.email)
        mock_send.assert_not_called()

    @patch("apps.accounts.services.send_mail", side_effect=RuntimeError("SMTP failure"))
    def test_failed_delivery_consumes_the_challenge_without_exposing_provider_error(self, mock_send):
        from .services import send_email_verification_code

        with self.assertRaises(EmailDeliveryUnavailable):
            send_email_verification_code(user=self.user, ip_address="127.0.0.1")
        challenge = OTPChallenge.objects.get()
        self.assertIsNotNone(challenge.consumed_at)
        mock_send.assert_called_once()
