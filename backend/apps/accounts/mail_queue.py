"""A database outbox for login/recovery requests; generated codes stay in memory."""
import uuid
from datetime import timedelta
from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from .models import DeferredMail, LoginChallenge, User
from .otp_utils import normalize_btu_email, normalize_client_ip


def enqueue(email, purpose, client_ip):
    from .persistent_otp import check_configuration, take_rate
    key = check_configuration()
    try:
        email = normalize_btu_email(email)
    except ValueError:
        return
    ip = normalize_client_ip(client_ip)
    with transaction.atomic():
        if not take_rate(key, 'mail-queue-ip', ip, timezone.now(), 30):
            return
        job, _ = DeferredMail.objects.get_or_create(recipient=email, purpose=purpose, defaults={'client_ip': ip})
        job = DeferredMail.objects.select_for_update().get(pk=job.pk)
        now = timezone.now()
        if job.request_count and now - job.requested_at < timedelta(seconds=60):
            return
        if now - job.window_started_at >= timedelta(hours=1):
            job.window_started_at, job.request_count = now, 0
        if job.request_count >= 5:
            return
        job.request_count += 1
        job.requested_at, job.next_attempt_at = now, now
        job.state, job.attempts, job.error_code = 'PENDING', 0, ''
        job.client_ip, job.token, job.lease_expires_at = ip, uuid.uuid4(), None
        job.save()


def deliver_one():
    from .persistent_otp import _send_login_code_now, eligible, check_configuration, digest
    from .services import _send_password_reset_now
    key = check_configuration()
    if connection.in_atomic_block:
        raise RuntimeError('Delivery requires autocommit; SMTP must not hold database locks.')
    with transaction.atomic():
        now = timezone.now()
        job = DeferredMail.objects.select_for_update(skip_locked=True).filter(
            Q(state='PENDING', next_attempt_at__lte=now) | Q(state='SENDING', lease_expires_at__lte=now)
        ).order_by('next_attempt_at', 'pk').first()
        if job is None:
            return False
        if job.attempts >= 3 or now - job.requested_at >= timedelta(minutes=5):
            job.state, job.error_code = 'FAILED', 'EXPIRED'
            job.save()
            return True
        job.state, job.lease_expires_at = 'SENDING', now + timedelta(seconds=60)
        job.attempts += 1
        job.save()
        pk, token = job.pk, job.token
    succeeded, error = False, ''
    try:
        if job.purpose == 'LOGIN':
            if not eligible(job.recipient):
                succeeded = True  # Unknown/inactive identities never receive a code.
            else:
                _send_login_code_now(job.recipient, client_ip=job.client_ip)
                challenge = LoginChallenge.objects.filter(pk=digest(key, 'email', job.recipient)).first()
                succeeded = bool(challenge and challenge.consumed_at is None and challenge.expires_at > timezone.now())
        else:
            succeeded = _send_password_reset_now(email=job.recipient, ip_address=job.client_ip) is not False
    except Exception:
        error = 'DELIVERY_FAILED'  # Never retain provider exceptions, bodies or codes.
    with transaction.atomic():
        current = DeferredMail.objects.select_for_update().get(pk=pk)
        if current.token == token:
            current.state = 'SENT' if succeeded else ('FAILED' if current.attempts >= 3 else 'PENDING')
            current.error_code = '' if succeeded else (error or 'DELIVERY_FAILED')
            current.next_attempt_at = timezone.now() + timedelta(seconds=60 * 2 ** current.attempts)
            current.lease_expires_at = None
            current.save()
    return True
