
import hmac
import re
import secrets

from django.conf import settings
from django.utils.crypto import salted_hmac


BTU_DOMAIN = "btu.edu.ge"


def normalize_btu_email(email):
    """Validate and normalize a BTU email."""

    if not isinstance(email, str):
        raise ValueError("Invalid email")

    email = email.strip().lower()

    if not re.fullmatch(
        r"[a-z0-9._%+\-]+@btu\.edu\.ge",
        email,
    ):
        raise ValueError("A valid BTU email is required")

    return email


def generate_otp():
    """Generate a cryptographically secure 6-digit OTP."""

    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(email, code):
    """Hash an OTP with the server secret."""

    email = normalize_btu_email(email)

    return salted_hmac(
        "accounts.otp",
        f"{email}:{code}",
        secret=settings.SECRET_KEY,
        algorithm="sha256",
    ).hexdigest()


def verify_otp_hash(email, code, stored_hash):
    """Compare the supplied OTP with its stored hash."""

    if (
        not isinstance(code, str)
        or not re.fullmatch(r"[0-9]{6}", code)
    ):
        return False

    if not isinstance(stored_hash, str):
        return False

    candidate_hash = hash_otp(email, code)

    return hmac.compare_digest(
        candidate_hash,
        stored_hash,
    )
