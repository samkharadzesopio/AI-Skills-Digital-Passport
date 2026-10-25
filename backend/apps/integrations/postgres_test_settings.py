"""Isolated loopback PostgreSQL only; never loads .env or DATABASE_URL."""
import getpass
from apps.accounts.test_settings import *  # noqa: F403

INSTALLED_APPS += ['apps.credentials', 'apps.passports', 'apps.integrations', 'apps.verification']
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql', 'HOST': '127.0.0.1', 'PORT': '55432',
    'NAME': 'classroom_tests', 'USER': getpass.getuser(),
    'TEST': {'NAME': 'test_classroom_automation'},
}}
ROOT_URLCONF = 'config.auth_test_urls'
TEST_RUNNER = 'config.foundation_test_runner.FoundationPostgresRunner'
ACCOUNTS_ALLOW_UNSAFE_TEST_DB = False

# Match both explicit synthetic status spellings used by existing regression suites.
ACCOUNTS_ACTIVE_STUDENT_STATUSES = ['ACTIVE', 'Active']
