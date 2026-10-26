"""Authentication test settings restricted to an explicit loopback PostgreSQL."""

from config.foundation_test_settings import *  # noqa: F403
import os
import secrets

INSTALLED_APPS += [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "apps.accounts.apps.AccountsConfig",
    "apps.integrations",
    "apps.verification.apps.VerificationConfig",
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "postgres",
        "USER": "postgres",
        "PASSWORD": "",
        "HOST": "127.0.0.1",
        "PORT": int(os.environ["AUTH_TEST_PG_PORT"]),
        "OPTIONS": {"connect_timeout": 5},
        "TEST": {"NAME": "test_auth_foundation"},
    }
}
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "apps.accounts.authentication.StudentOTPBackend",
    "apps.accounts.authentication.AdminPasswordBackend",
]
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.accounts.authentication.AccountSessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "apps.accounts.permissions.IsVerifiedAuthenticated",
    ],
    "UNAUTHENTICATED_USER": None,
}
ROOT_URLCONF = "config.auth_test_urls"
TEST_RUNNER = "config.foundation_test_runner.FoundationPostgresRunner"
SECRET_KEY = secrets.token_urlsafe(48)
ACCOUNTS_OTP_HMAC_KEY = secrets.token_hex(32)
ACCOUNTS_ACTIVE_STUDENT_STATUSES = ["ACTIVE", "Active"]
ACCOUNTS_ALLOW_TEST_EMAIL = True
ACCOUNTS_ALLOW_UNSAFE_TEST_DB = False
OTP_PEPPER = secrets.token_hex(32)
AUTH_TOKEN_PEPPER = OTP_PEPPER
ALLOWED_HOSTS = ["testserver", "localhost"]
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "no-reply@btu.edu.ge"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
]

# Explicit public-verification policy for the synthetic fixed BTU issuer.
VERIFICATION_TRUSTED_ISSUER_REFERENCES = ['BTU-UNIVERSITY']
