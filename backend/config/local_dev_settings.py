"""Explicit local profile; never select for deployment.

Keeps all authentication, CSRF, ownership, row locks and permissions. Only the
named loopback development database and private file mailbox are permitted.
Normal config.settings retains mandatory production TLS/SMTP behavior.
"""
import os
from .settings import *  # noqa: F403
from .local_dev_policy import local_database

DATABASES = {'default': local_database(DATABASES['default'], enabled=os.environ.get('BTU_LOCAL_DEVELOPMENT'), debug=DEBUG)}
if not ACCOUNTS_ACTIVE_STUDENT_STATUSES:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured('Set ACCOUNTS_ACTIVE_STUDENT_STATUSES explicitly in the local .env.')

ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
CSRF_TRUSTED_ORIGINS = []  # Vite preserves Host/Origin; no cross-origin exception needed.
EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
EMAIL_FILE_PATH = BASE_DIR / '.local-mail'
# Allows local file delivery and HTTP loopback cookies in this guarded profile.
# It does not skip OTP validation, account eligibility or PostgreSQL row locks.
ACCOUNTS_ALLOW_TEST_EMAIL = True
