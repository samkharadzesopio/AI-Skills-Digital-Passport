"""Disposable local PostgreSQL ONLY; never reads DATABASE_URL or backend/.env.

Start your own local PostgreSQL instance on 127.0.0.1:55432 with a
passport_auth_tests database owned by the current OS user, then run:
python manage.py test apps.accounts --settings=apps.accounts.postgres_test_settings
"""
import getpass
from .test_settings import *  # noqa: F403

ACCOUNTS_ALLOW_UNSAFE_TEST_DB = False
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'HOST': '127.0.0.1', 'PORT': '55432',
    'NAME': 'passport_auth_tests', 'USER': getpass.getuser(),
}}
