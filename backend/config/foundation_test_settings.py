"""Explicit local PostgreSQL only; never loads .env or the Neon DATABASE_URL."""

import os

from django.core.exceptions import ImproperlyConfigured

from apps.skills.test_settings import *  # noqa: F403

INSTALLED_APPS += ["apps.credentials.apps.CredentialsConfig"]
INSTALLED_APPS += ["apps.passports.apps.PassportsConfig"]
INSTALLED_APPS += ["apps.blockchain.apps.BlockchainConfig"]
# Legacy domain regressions exercise registry behavior separately from the new
# real-Anvil lifecycle tests, which explicitly enforce chain confirmation.
PASSPORT_BLOCKCHAIN_ENFORCE = False

if os.environ.get("FOUNDATION_TEST_PG_HOST") != "127.0.0.1":
    raise ImproperlyConfigured("Foundation tests require an explicit 127.0.0.1 host.")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": "127.0.0.1",
        "PORT": int(os.environ["FOUNDATION_TEST_PG_PORT"]),
        "NAME": "foundation_test",
        "USER": "passport_test",
        "PASSWORD": os.environ["FOUNDATION_TEST_PG_PASSWORD"],
        "OPTIONS": {"connect_timeout": 5},
        "TEST": {"NAME": "test_foundation_test"},
    },
}

ROOT_URLCONF = "config.urls"
TEST_RUNNER = "config.foundation_test_runner.FoundationPostgresRunner"
