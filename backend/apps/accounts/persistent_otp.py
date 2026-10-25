"""Persistent OTP login. Legacy otp_store/services are development-only, unused here."""
import hashlib
import hmac
import re
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import send_mail
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from apps.students.models import Student
from .identity import active_student_statuses, provision_student_account
from .models import LoginChallenge, LoginRateBucket, User
from .otp_utils import generate_otp, normalize_btu_email

GENERIC_REQUEST_MESSAGE = 'If eligible, a login code will be sent to your registered email.'


def check_configuration():
    key = getattr(settings, 'ACCOUNTS_OTP_HMAC_KEY', '')
    if not isinstance(key, str) or len(key) < 32:
        raise ImproperlyConfigured('ACCOUNTS_OTP_HMAC_KEY must contain at least 32 characters.')
    active_student_statuses()
    if not settings.SECRET_KEY or settings.SECRET_KEY.startswith('django-insecure-'):
        raise ImproperlyConfigured('A private Django SECRET_KEY is required.')
    if not getattr(settings, 'ACCOUNTS_ALLOW_TEST_EMAIL', False) and not (
        getattr(settings, 'SESSION_COOKIE_SECURE', False)
        and getattr(settings, 'CSRF_COOKIE_SECURE', False)
        and getattr(settings, 'SESSION_ENGINE', '') == 'django.contrib.sessions.backends.db'
    ):
        raise ImproperlyConfigured('Secure cookies and database sessions are required.')
    if not connection.features.has_select_for_update and not getattr(
        settings, 'ACCOUNTS_ALLOW_UNSAFE_TEST_DB', False
    ):
        raise ImproperlyConfigured('OTP login requires database row locking (PostgreSQL).')
    backend = getattr(settings, 'EMAIL_BACKEND', '')
    if not getattr(settings, 'ACCOUNTS_ALLOW_TEST_EMAIL', False) and (
        backend != 'django.core.mail.backends.smtp.EmailBackend'
        or not getattr(settings, 'EMAIL_HOST', '')
        or not getattr(settings, 'DEFAULT_FROM_EMAIL', '')
        or not (getattr(settings, 'EMAIL_USE_TLS', False)
                or getattr(settings, 'EMAIL_USE_SSL', False))
    ):
        raise ImproperlyConfigured('OTP delivery requires configured TLS SMTP; console email is forbidden.')
    return key.encode()


def digest(key, *parts):
    return hmac.new(key, '\x00'.join(map(str, parts)).encode(), hashlib.sha256).hexdigest()


def take_rate(key, scope, identity, now, limit):
    bucket_key = digest(key, scope, identity)
    LoginRateBucket.objects.get_or_create(key=bucket_key, defaults={'window_started_at': now})
    bucket = LoginRateBucket.objects.select_for_update().get(pk=bucket_key)
    now = timezone.now()  # Evaluate the window after any lock wait.
    if now - bucket.window_started_at >= timedelta(hours=1):
        bucket.window_started_at, bucket.count = now, 0
    if bucket.count >= limit:
        return False
    bucket.count += 1
    bucket.save()
    return True


def eligible(email):
    student = Student.objects.filter(
        email__iexact=email, student_status__in=active_student_statuses(),
    ).first()
    if not student:
        return False
    account = User.objects.filter(email__iexact=email).first()
    if account:
        return bool(account.is_active and not account.is_staff and not account.is_superuser
                    and account.student_id == student.pk)
    return not User.objects.filter(student=student).exists()


@transaction.atomic
def request_login_code(email, *, client_ip):
    key = check_configuration()
    now = timezone.now()
    if not take_rate(key, 'request-ip', client_ip, now, 30):
        return GENERIC_REQUEST_MESSAGE
    try:
        email = normalize_btu_email(email)
    except ValueError:
        return GENERIC_REQUEST_MESSAGE
    subject = digest(key, 'email', email)
    LoginChallenge.objects.get_or_create(subject=subject)
    challenge = LoginChallenge.objects.select_for_update().get(pk=subject)
    now = timezone.now()  # Cooldown and expiry must use the time after locking.
    if challenge.last_requested_at and now - challenge.last_requested_at < timedelta(seconds=60):
        return GENERIC_REQUEST_MESSAGE
    if not challenge.window_started_at or now - challenge.window_started_at >= timedelta(hours=1):
        challenge.window_started_at, challenge.request_count = now, 0
    if challenge.request_count >= 5:
        return GENERIC_REQUEST_MESSAGE
    challenge.request_count += 1
    challenge.last_requested_at = now
    challenge.nonce = uuid.uuid4()
    code = generate_otp()
    challenge.code_hash = digest(key, 'code', subject, challenge.nonce, code)
    challenge.attempts = 0
    challenge.expires_at = now + timedelta(minutes=5)
    challenge.consumed_at = now
    if eligible(email):
        try:
            delivered = send_mail(
                'BTU Digital Passport - Login Code',
                f'Your verification code is: {code}\nIt expires in 5 minutes.',
                settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False,
            )
            if delivered == 1:
                challenge.consumed_at = None
        except Exception:
            # Do not log exception text: delivery providers may echo the message/code.
            # Leave the challenge consumed and retain cooldown on delivery failure.
            pass
    challenge.save()
    return GENERIC_REQUEST_MESSAGE


@transaction.atomic
def consume_login_code(email, code, *, client_ip):
    key = check_configuration()
    now = timezone.now()
    if not take_rate(key, 'verify-ip', client_ip, now, 60):
        return None
    try:
        email = normalize_btu_email(email)
    except ValueError:
        return None
    subject = digest(key, 'email', email)
    challenge = LoginChallenge.objects.select_for_update().filter(pk=subject).first()
    # Lock acquisition can block: evaluate expiry using the time AFTER acquiring it.
    now = timezone.now()
    if not challenge or challenge.consumed_at or not challenge.expires_at or (
        now >= challenge.expires_at or challenge.attempts >= 5
    ):
        return None
    challenge.attempts += 1
    challenge.save(update_fields=['attempts'])
    if not isinstance(code, str) or not re.fullmatch(r'[0-9]{6}', code):
        return None
    if not hmac.compare_digest(challenge.code_hash, digest(key, 'code', subject, challenge.nonce, code)):
        return None
    try:
        user = provision_student_account(email)
    except PermissionDenied:
        challenge.consumed_at = now
        challenge.save(update_fields=['consumed_at'])
        return None
    challenge.consumed_at = now
    challenge.save(update_fields=['consumed_at'])
    return user
