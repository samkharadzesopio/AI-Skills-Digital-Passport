"""Bound rendering requests across workers using the existing account counters."""
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.throttling import BaseThrottle

from apps.accounts.models import AuthRateLimitBucket
from apps.accounts.otp_utils import security_digest


class PDFGenerationThrottle(BaseThrottle):
    def allow_request(self, request, view):
        if request.method != 'POST':
            return True
        if connection.vendor != 'postgresql':
            raise ImproperlyConfigured('PDF generation throttling requires PostgreSQL.')
        try:
            limit = int(getattr(settings, 'PASSPORT_PDF_REQUESTS_PER_MINUTE', 6))
        except (TypeError, ValueError):
            raise ImproperlyConfigured('PDF request limit must be an integer.') from None
        if not 1 <= limit <= 1000:
            raise ImproperlyConfigured('PDF request limit must be between 1 and 1000.')
        key = security_digest('passport.pdf.requests.v1', str(request.user.pk))
        with transaction.atomic():
            AuthRateLimitBucket.objects.get_or_create(bucket_digest=key)
            bucket = AuthRateLimitBucket.objects.select_for_update().get(pk=key)
            now = timezone.now()
            if now - bucket.window_started_at >= timedelta(minutes=1):
                bucket.window_started_at, bucket.request_count = now, 0
            self.remaining = max(1, 60 - (now - bucket.window_started_at).total_seconds())
            if bucket.request_count >= limit:
                return False
            bucket.request_count += 1
            bucket.save(update_fields=['window_started_at', 'request_count', 'updated_at'])
        return True

    def wait(self):
        return self.remaining
