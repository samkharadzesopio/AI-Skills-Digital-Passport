"""Shared-worker limits using the existing persistent security counter model."""
from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadhandler import FileUploadHandler
from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, ParseError
from rest_framework.throttling import BaseThrottle

from apps.accounts.models import AuthRateLimitBucket
from apps.accounts.otp_utils import normalize_client_ip, security_digest
from .document_service import MAX_PDF_SIZE


class UploadTooLarge(APIException):
    status_code = 413
    default_detail = 'Verification upload exceeds the size limit.'


class VerificationThrottle(BaseThrottle):
    def allow_request(self, request, view):
        if connection.vendor != 'postgresql':
            raise ImproperlyConfigured('Public verification throttling requires PostgreSQL.')
        scope = view.verification_scope
        # Deliberately ignore spoofable forwarding headers.
        ip = normalize_client_ip(request.META.get('REMOTE_ADDR'))
        key = security_digest('verification.rate-limit.v1', f'{scope}:{ip}')
        limit = 10 if scope == 'pdf' else 60
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


class BoundedVerificationUpload(FileUploadHandler):
    def __init__(self, request):
        super().__init__(request)
        self.total = 0

    def receive_data_chunk(self, raw_data, start):
        self.total += len(raw_data)
        if self.total > MAX_PDF_SIZE:
            raise UploadTooLarge()
        return raw_data

    def file_complete(self, file_size):
        return None


def install_upload_limits(request):
    try:
        length = int(request.META.get('CONTENT_LENGTH') or 0)
    except (TypeError, ValueError):
        raise ParseError('Invalid request length.') from None
    if length < 0:
        raise ParseError('Invalid request length.')
    if length > MAX_PDF_SIZE + 65536:
        raise UploadTooLarge()
    request._request.upload_handlers.insert(0, BoundedVerificationUpload(request._request))
