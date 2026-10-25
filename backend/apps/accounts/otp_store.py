from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import AuthRateLimitBucket, OTPChallenge
from .otp_utils import (
    generate_otp,
    hash_otp,
    normalize_btu_email,
    normalize_client_ip,
    security_digest,
    verify_otp_hash,
)


class AuthRateLimitExceeded(Exception):
    pass


def _consume_budgets(*, scope, email_digest, ip_digest, email_limit, ip_limit, now):
    window = int(getattr(settings, "AUTH_RATE_LIMIT_WINDOW_SECONDS", 900))
    if window < 1:
        raise ValueError("Authentication rate-limit window must be positive.")
    keyed_limits = {
        security_digest("accounts.rate-limit", f"{scope}:email:{email_digest}"): email_limit,
        security_digest("accounts.rate-limit", f"{scope}:ip:{ip_digest}"): ip_limit,
    }
    for digest in sorted(keyed_limits):
        AuthRateLimitBucket.objects.get_or_create(
            bucket_digest=digest,
            defaults={"window_started_at": now, "request_count": 0},
        )
    rows = list(
        AuthRateLimitBucket.objects.select_for_update()
        .filter(bucket_digest__in=keyed_limits)
        .order_by("bucket_digest")
    )
    if len(rows) != len(keyed_limits):
        raise RuntimeError("Authentication rate-limit state is unavailable.")

    now = timezone.now()  # Window checks follow row-lock acquisition.
    exceeded = False
    for row in rows:
        limit = keyed_limits[row.bucket_digest]
        if now - row.window_started_at >= timedelta(seconds=window):
            row.window_started_at = now
            row.request_count = 0
        if row.request_count >= limit:
            exceeded = True
    if exceeded:
        raise AuthRateLimitExceeded
    for row in rows:
        row.request_count += 1
        row.save(update_fields=["window_started_at", "request_count", "updated_at"])


def consume_login_budget(email, ip_address, *, now=None):
    email = normalize_btu_email(email)
    ip_address = normalize_client_ip(ip_address)
    email_digest = security_digest("accounts.email", email)
    ip_digest = security_digest("accounts.ip", ip_address)
    now = now or timezone.now()
    with transaction.atomic():
        _consume_budgets(
            scope="login",
            email_digest=email_digest,
            ip_digest=ip_digest,
            email_limit=int(getattr(settings, "AUTH_LOGIN_EMAIL_ATTEMPTS_PER_WINDOW", 10)),
            ip_limit=int(getattr(settings, "AUTH_LOGIN_IP_ATTEMPTS_PER_WINDOW", 30)),
            now=now,
        )


def consume_otp_locked(*, email, purpose, code, now=None):
    """Consume or count an OTP attempt; caller must hold transaction.atomic()."""

    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("OTP consumption requires a database transaction.")
    email = normalize_btu_email(email)
    email_digest = security_digest("accounts.email", email)
    now = now or timezone.now()
    challenge = (
        OTPChallenge.objects.select_for_update()
        .filter(
            email_digest=email_digest,
            purpose=purpose,
            consumed_at__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )
    if challenge is None:
        return False

    max_attempts = int(getattr(settings, "AUTH_OTP_MAX_ATTEMPTS", 5))
    if now >= challenge.expires_at or challenge.attempts >= max_attempts:
        challenge.consumed_at = now
        challenge.save(update_fields=["consumed_at"])
        return False

    challenge.attempts += 1
    valid = verify_otp_hash(email, code, challenge.code_digest, purpose)
    if valid or challenge.attempts >= max_attempts:
        challenge.consumed_at = now
    challenge.save(update_fields=["attempts", "consumed_at"])
    return valid


class OTPStore:
    """Compatibility facade backed by PostgreSQL rows, safe across workers."""

    def issue(self, email, *, purpose=OTPChallenge.Purpose.EMAIL_VERIFY, ip_address="unknown"):
        email = normalize_btu_email(email)
        if purpose not in OTPChallenge.Purpose.values:
            raise ValueError("Unsupported OTP purpose.")
        ip_address = normalize_client_ip(ip_address)
        code = generate_otp()
        now = timezone.now()
        email_digest = security_digest("accounts.email", email)
        ip_digest = security_digest("accounts.ip", ip_address)
        expiry = int(getattr(settings, "AUTH_OTP_EXPIRY_SECONDS", 300))
        if expiry < 1:
            raise ValueError("OTP expiry must be positive.")
        with transaction.atomic():
            _consume_budgets(
                scope=f"otp:{purpose}",
                email_digest=email_digest,
                ip_digest=ip_digest,
                email_limit=int(getattr(settings, "AUTH_OTP_EMAIL_REQUESTS_PER_WINDOW", 3)),
                ip_limit=int(getattr(settings, "AUTH_OTP_IP_REQUESTS_PER_WINDOW", 20)),
                now=now,
            )
            OTPChallenge.objects.filter(
                email_digest=email_digest,
                purpose=purpose,
                consumed_at__isnull=True,
            ).update(consumed_at=now)
            OTPChallenge.objects.create(
                purpose=purpose,
                email_digest=email_digest,
                ip_digest=ip_digest,
                code_digest=hash_otp(email, code, purpose),
                expires_at=now + timedelta(seconds=expiry),
            )
        return code

    def verify(self, email, code, *, purpose=OTPChallenge.Purpose.EMAIL_VERIFY):
        with transaction.atomic():
            return consume_otp_locked(email=email, purpose=purpose, code=code)


otp_store = OTPStore()
