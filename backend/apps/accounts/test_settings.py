"""Isolated auth integration tests. Never imports config.settings or DATABASE_URL."""
import secrets

SECRET_KEY = secrets.token_hex(32)
ACCOUNTS_OTP_HMAC_KEY = secrets.token_hex(32)
ACCOUNTS_ACTIVE_STUDENT_STATUSES = ['ACTIVE']  # Synthetic test contract only.
ACCOUNTS_ALLOW_UNSAFE_TEST_DB = True
ACCOUNTS_ALLOW_TEST_EMAIL = True
INSTALLED_APPS = [
    'django.contrib.contenttypes', 'django.contrib.auth', 'django.contrib.sessions',
    'rest_framework', 'apps.students', 'apps.skills', 'apps.accounts',
]
AUTH_USER_MODEL = 'accounts.User'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
ROOT_URLCONF = 'apps.accounts.test_urls'
MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
]
AUTHENTICATION_BACKENDS = [
    'apps.accounts.authentication.StudentOTPBackend',
    'apps.accounts.authentication.AdminPasswordBackend',
]
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['apps.accounts.authentication.AccountSessionAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
DEFAULT_FROM_EMAIL = 'passport@btu.edu.ge'
ALLOWED_HOSTS = ['testserver', 'localhost']
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 1800
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
