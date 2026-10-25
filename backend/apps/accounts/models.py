import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from apps.students.models import Student

from .managers import UserManager


ADMIN_PERMISSION_CODENAMES = frozenset(
    {
        "access_admin_api",
        "manage_student_accounts",
        "view_student_records",
        "manage_credentials",
        "revoke_credentials",
        "sync_classroom",
        "import_completions",
    }
)


class User(AbstractUser):
    class Role(models.TextChoices):
        STUDENT = "STUDENT", "Student"
        ADMIN = "ADMIN", "Administrator"

    # Preserve Developer 2's existing usernames while allowing new accounts to
    # use email-only sign-in without generating a second login identifier.
    username = models.CharField(max_length=150, blank=True, null=True, unique=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=254, unique=True)
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.STUDENT)
    is_email_verified = models.BooleanField(default=False)
    student = models.OneToOneField(
        Student,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="login_account",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        db_table = "accounts_user"
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_email_ci_unique"),
            models.CheckConstraint(
                condition=(
                    models.Q(student__isnull=True)
                    | models.Q(is_staff=False, is_superuser=False)
                ),
                name="accounts_student_not_admin",
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=["STUDENT", "ADMIN"]),
                name="chk_accounts_user_role",
            ),
            models.CheckConstraint(
                condition=models.Q(email=Lower("email")),
                name="chk_accounts_user_email_lower",
            ),
            models.CheckConstraint(
                condition=models.Q(email__regex=r"^[a-z0-9._%+\-]+@btu\.edu\.ge$"),
                name="chk_accounts_user_email_btu",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(role="STUDENT", is_staff=False, is_superuser=False)
                    | models.Q(role="ADMIN", is_staff=True, is_superuser=False)
                ),
                name="chk_accounts_user_role_privileges",
            ),
        ]
        permissions = [
            (codename, f"Can {codename.replace('_', ' ')}")
            for codename in sorted(ADMIN_PERMISSION_CODENAMES)
        ]

    def save(self, *args, **kwargs):
        if isinstance(self.email, str):
            self.email = self.email.strip().lower()
        return super().save(*args, **kwargs)


class StudentAccountInvitation(models.Model):
    """Single active, university-provisioned email-to-student invitation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.OneToOneField(
        Student,
        on_delete=models.PROTECT,
        related_name="account_invitation",
    )
    token_digest = models.CharField(max_length=64, unique=True)
    recipient_email_digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    redeemed_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="student_account_invitations",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "student_account_invitations"
        indexes = [models.Index(fields=["expires_at"], name="acct_invite_expiry_idx")]
        constraints = [
            models.CheckConstraint(
                condition=~(
                    models.Q(redeemed_at__isnull=False)
                    & models.Q(revoked_at__isnull=False)
                ),
                name="chk_invitation_single_terminal_state",
            ),
            models.CheckConstraint(
                condition=models.Q(token_digest__regex=r"^[0-9a-f]{64}$"),
                name="chk_invitation_token_hash",
            ),
            models.CheckConstraint(
                condition=models.Q(recipient_email_digest__regex=r"^[0-9a-f]{64}$"),
                name="chk_invitation_email_hash",
            ),
        ]


class OTPChallenge(models.Model):
    class Purpose(models.TextChoices):
        EMAIL_VERIFY = "EMAIL_VERIFY", "Email verification"
        PASSWORD_RESET = "PASSWORD_RESET", "Password reset"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    email_digest = models.CharField(max_length=64)
    ip_digest = models.CharField(max_length=64)
    code_digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "account_otp_challenges"
        indexes = [
            models.Index(
                fields=["email_digest", "purpose", "created_at"],
                name="otp_email_purpose_time_idx",
            ),
            models.Index(fields=["expires_at"], name="otp_expiry_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["email_digest", "purpose"],
                condition=models.Q(consumed_at__isnull=True),
                name="uq_otp_active_email_purpose",
            ),
            models.CheckConstraint(
                condition=models.Q(purpose__in=["EMAIL_VERIFY", "PASSWORD_RESET"]),
                name="chk_otp_purpose",
            ),
            models.CheckConstraint(
                condition=models.Q(email_digest__regex=r"^[0-9a-f]{64}$"),
                name="chk_otp_email_hash",
            ),
            models.CheckConstraint(
                condition=models.Q(ip_digest__regex=r"^[0-9a-f]{64}$"),
                name="chk_otp_ip_hash",
            ),
            models.CheckConstraint(
                condition=models.Q(code_digest__regex=r"^[0-9a-f]{64}$"),
                name="chk_otp_code_hash",
            ),
            models.CheckConstraint(
                condition=models.Q(attempts__lte=5),
                name="chk_otp_attempt_limit",
            ),
        ]


class AuthRateLimitBucket(models.Model):
    """Persistent hashed principal counters shared across Django workers."""

    bucket_digest = models.CharField(max_length=64, primary_key=True)
    window_started_at = models.DateTimeField(default=timezone.now)
    request_count = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account_auth_rate_buckets"
        indexes = [models.Index(fields=["window_started_at"], name="auth_bucket_window_idx")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(bucket_digest__regex=r"^[0-9a-f]{64}$"),
                name="chk_auth_bucket_hash",
            ),
            models.CheckConstraint(
                condition=models.Q(request_count__gte=0),
                name="chk_auth_bucket_count",
            ),
        ]


class LoginChallenge(models.Model):
    """Persistent OTP login challenge from the initial account foundation."""

    subject = models.CharField(max_length=64, primary_key=True)
    nonce = models.UUIDField(default=uuid.uuid4)
    code_hash = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField(null=True)
    consumed_at = models.DateTimeField(null=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_requested_at = models.DateTimeField(null=True)
    window_started_at = models.DateTimeField(null=True)
    request_count = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["expires_at"], name="login_challenge_expiry_idx")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(attempts__lte=5),
                name="chk_login_challenge_attempts",
            ),
        ]


class LoginRateBucket(models.Model):
    """Hashed IP rate counters for the persistent student OTP login API."""

    key = models.CharField(max_length=64, primary_key=True)
    window_started_at = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["window_started_at"], name="login_rate_bucket_window_idx")]
