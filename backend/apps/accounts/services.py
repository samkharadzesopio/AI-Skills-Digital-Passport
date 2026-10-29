import secrets
from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail, get_connection
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.students.models import Student

from .managers import normalize_login_email
from .models import OTPChallenge, StudentAccountInvitation, User
from .otp_store import AuthRateLimitExceeded, consume_otp_locked, consume_login_budget, otp_store
from .otp_utils import hash_otp, normalize_btu_email, security_digest


class InvalidInvitation(Exception):
    pass


class InvalidRecoveryCode(Exception):
    pass


class EmailDeliveryUnavailable(Exception):
    pass


def _require_btu_email(email):
    return normalize_btu_email(normalize_login_email(email))


def _invitation_digest(token):
    return security_digest("accounts.invitation", token)


@transaction.atomic
def create_student_account_invitation(*, student_id, actor):
    from .authorization import has_admin_permission

    if not has_admin_permission(actor, "accounts.manage_student_accounts"):
        raise PermissionDenied("Student account provisioning permission required.")
    try:
        student_uuid = UUID(str(student_id))
    except (TypeError, ValueError, AttributeError):
        raise Student.DoesNotExist from None

    student = Student.objects.select_for_update().filter(pk=student_uuid).first()
    if student is None:
        raise Student.DoesNotExist
    email = _require_btu_email(student.email)
    if User.objects.filter(student_id=student.pk).exists() or User.objects.filter(portal_only=False, email=email).exists():
        raise InvalidInvitation

    now = timezone.now()
    invitation = (
        StudentAccountInvitation.objects.select_for_update()
        .filter(student_id=student.pk)
        .first()
    )
    if (
        invitation
        and invitation.redeemed_at is None
        and invitation.revoked_at is None
        and invitation.expires_at > now
    ):
        raise InvalidInvitation

    token = secrets.token_urlsafe(32)
    expires = now + timedelta(
        seconds=int(getattr(settings, "STUDENT_INVITATION_EXPIRY_SECONDS", 86400))
    )
    values = {
        "token_digest": _invitation_digest(token),
        "recipient_email_digest": security_digest("accounts.email", email),
        "expires_at": expires,
        "redeemed_at": None,
        "revoked_at": None,
        "created_by": actor,
    }
    if invitation is None:
        invitation = StudentAccountInvitation.objects.create(
            student=student,
            **values,
        )
    else:
        for field, value in values.items():
            setattr(invitation, field, value)
        invitation.save(update_fields=list(values))
    return invitation, token, email


def revoke_student_account_invitation(invitation_id):
    now = timezone.now()
    with transaction.atomic():
        invitation = StudentAccountInvitation.objects.select_for_update().get(pk=invitation_id)
        if invitation.redeemed_at is None and invitation.revoked_at is None:
            invitation.revoked_at = now
            invitation.save(update_fields=["revoked_at"])


def redeem_student_account_invitation(*, token, password):
    if not isinstance(token, str) or not token or len(token) > 128:
        raise InvalidInvitation
    digest = _invitation_digest(token)
    student_id = (
        StudentAccountInvitation.objects.filter(token_digest=digest)
        .values_list("student_id", flat=True)
        .first()
    )
    if student_id is None:
        raise InvalidInvitation

    initial_student = Student.objects.only("id", "email").filter(pk=student_id).first()
    if initial_student is None:
        raise InvalidInvitation
    try:
        email = _require_btu_email(initial_student.email)
        validate_password(password, user=User(email=email))
    except (ValidationError, TypeError, ValueError):
        raise

    try:
        with transaction.atomic():
            student = Student.objects.select_for_update().filter(pk=student_id).first()
            invitation = (
                StudentAccountInvitation.objects.select_for_update()
                .filter(student_id=student_id, token_digest=digest)
                .first()
            )
            now = timezone.now()
            if (
                student is None
                or invitation is None
                or invitation.redeemed_at is not None
                or invitation.revoked_at is not None
                or invitation.expires_at <= now
            ):
                raise InvalidInvitation
            email = _require_btu_email(student.email)
            if not secrets.compare_digest(
                invitation.recipient_email_digest,
                security_digest("accounts.email", email),
            ):
                raise InvalidInvitation
            if User.objects.filter(student_id=student.pk).exists() or User.objects.filter(portal_only=False, email=email).exists():
                raise InvalidInvitation
            user = User.objects.create_user(
                email=email,
                password=password,
                role=User.Role.STUDENT,
                is_email_verified=True,
                student=student,
            )
            invitation.redeemed_at = now
            invitation.save(update_fields=["redeemed_at"])
            return user
    except IntegrityError:
        # Unique Student and email constraints remain the final concurrency guard.
        raise InvalidInvitation from None


def issue_otp(email, *, purpose, ip_address):
    email = _require_btu_email(email)
    return otp_store.issue(email, purpose=purpose, ip_address=ip_address)


def send_email_verification_code(*, user, ip_address):
    if not user or not user.is_authenticated or not user.is_active:
        return
    if user.is_email_verified:
        return
    email = _require_btu_email(user.email)
    code = issue_otp(
        email,
        purpose=OTPChallenge.Purpose.EMAIL_VERIFY,
        ip_address=ip_address,
    )
    try:
        delivered = send_mail(
            subject="BTU Digital Passport - Email verification",
            message=f"Your verification code is {code}. It expires in 5 minutes.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
            connection=get_connection(timeout=10),
        )
    except Exception:
        delivered = 0
    if delivered != 1:
        OTPChallenge.objects.filter(
            email_digest=security_digest("accounts.email", email),
            purpose=OTPChallenge.Purpose.EMAIL_VERIFY,
            code_digest=hash_otp(email, code, OTPChallenge.Purpose.EMAIL_VERIFY),
            consumed_at__isnull=True,
        ).update(consumed_at=timezone.now())
        raise EmailDeliveryUnavailable from None


def send_verification_email(email, ip_address="unknown"):
    """Backward-compatible internal entry point; never creates public accounts."""

    email = _require_btu_email(email)
    user = User.objects.filter(portal_only=False, email=email, is_active=True, is_email_verified=False).first()
    if user is not None:
        send_email_verification_code(user=user, ip_address=ip_address)


def verify_verification_code(email, code):
    email = _require_btu_email(email)
    user = User.objects.filter(portal_only=False, email=email, is_active=True).first()
    if user is None or user.is_email_verified:
        return False
    return verify_email_code(user=user, code=code)


def verify_email_code(*, user, code):
    if not user or not user.is_authenticated:
        return False
    with transaction.atomic():
        locked = User.objects.select_for_update().filter(pk=user.pk, is_active=True).first()
        if locked is None or locked.is_email_verified:
            return False
        valid = consume_otp_locked(
            email=locked.email,
            purpose=OTPChallenge.Purpose.EMAIL_VERIFY,
            code=code,
        )
        if valid and not locked.is_email_verified:
            locked.is_email_verified = True
            locked.save(update_fields=["is_email_verified"])
        return valid


def request_password_reset(*, email, ip_address):
    if not getattr(settings, 'ACCOUNTS_ALLOW_TEST_EMAIL', False):
        from .mail_queue import enqueue
        enqueue(email, 'RESET', ip_address)
        return
    return _send_password_reset_now(email=email, ip_address=ip_address)


def _send_password_reset_now(*, email, ip_address):
    email = _require_btu_email(email)
    code = issue_otp(
        email,
        purpose=OTPChallenge.Purpose.PASSWORD_RESET,
        ip_address=ip_address,
    )
    user = User.objects.filter(portal_only=False, email=email, is_active=True, is_email_verified=True).only(
        "id", "email"
    ).first()
    if user is None:
        return
    try:
        delivered = send_mail(
            subject="BTU Digital Passport - Password reset code",
            message=f"Your password reset code is {code}. It expires in 5 minutes.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
            connection=get_connection(timeout=10),
        )
        if delivered != 1:
            raise EmailDeliveryUnavailable
        return True
    except Exception:
        email_digest = security_digest("accounts.email", email)
        OTPChallenge.objects.filter(
            email_digest=email_digest,
            purpose=OTPChallenge.Purpose.PASSWORD_RESET,
            code_digest=security_digest(
                "accounts.otp",
                f"{email}:{OTPChallenge.Purpose.PASSWORD_RESET}:{code}",
            ),
            consumed_at__isnull=True,
        ).update(consumed_at=timezone.now())

        return False


def reset_password_with_otp(*, email, code, new_password):
    email = _require_btu_email(email)
    try:
        validate_password(new_password)
    except ValidationError:
        raise
    with transaction.atomic():
        valid = consume_otp_locked(
            email=email,
            purpose=OTPChallenge.Purpose.PASSWORD_RESET,
            code=code,
        )
        user = User.objects.select_for_update().filter(
            email=email,
            is_active=True,
            is_email_verified=True,
        ).first()
        if not valid or user is None:
            raise InvalidRecoveryCode
        user.set_password(new_password)
        user.save(update_fields=["password"])
        return user


def send_invitation_email(*, email, token):
    send_mail(
        subject="BTU Digital Passport - Create your account",
        message=(
            "Use this single-use university invitation token to create your account:\n\n"
            f"{token}\n\nIt expires in 24 hours. If you did not expect this message, ignore it."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
            connection=get_connection(timeout=10),
    )


def check_login_rate_limit(email, ip_address):
    normalized = _require_btu_email(email)
    consume_login_budget(normalized, ip_address)
