
import hmac
import ipaddress
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


def _otp_secret():
    return getattr(settings, "OTP_PEPPER", None) or settings.SECRET_KEY


def security_digest(salt, value):
    return salted_hmac(salt, value, secret=_otp_secret(), algorithm="sha256").hexdigest()


def normalize_client_ip(value):
    if not isinstance(value, str):
        return "unknown"
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return "unknown"


def hash_otp(email, code, purpose="EMAIL_VERIFY"):
    """Hash an OTP with the server secret."""

    email = normalize_btu_email(email)

    return salted_hmac(
        "accounts.otp",
        f"{email}:{purpose}:{code}",
        secret=_otp_secret(),
        algorithm="sha256",
    ).hexdigest()


def verify_otp_hash(email, code, stored_hash, purpose="EMAIL_VERIFY"):
    """Compare the supplied OTP with its stored hash."""

    if (
        not isinstance(code, str)
        or not re.fullmatch(r"[0-9]{6}", code)
    ):
        return False

    if not isinstance(stored_hash, str):
        return False

    candidate_hash = hash_otp(email, code, purpose)

    return hmac.compare_digest(
        candidate_hash,
        stored_hash,
    )
