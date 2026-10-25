
from django.core.mail import send_mail

from .otp_store import OTPStore
from .otp_utils import normalize_btu_email


# Development-only in-memory OTP store.
otp_store = OTPStore()


def send_verification_email(email):
    email = normalize_btu_email(email)

    code = otp_store.issue(email)

    send_mail(
        subject="BTU Digital Passport - Login Code",
        message=(
            f"Your verification code is: {code}\n\n"
            "It expires in 5 minutes.\n"
            "If you didn't request this code, "
            "ignore this message."
        ),
        from_email="no-reply@example.com",
        recipient_list=[email],
        fail_silently=False,
    )


def verify_verification_code(email, code):
    email = normalize_btu_email(email)
    return otp_store.verify(email, code)
