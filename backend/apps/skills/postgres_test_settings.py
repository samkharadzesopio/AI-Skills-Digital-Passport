"""Opt-in tests for a disposable PostgreSQL cluster, never the shared service."""

import os

from .test_settings import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "postgres",
        "USER": "passport_test",
        "HOST": os.environ["SKILL_TEST_PG_HOST"],
        "PORT": os.environ["SKILL_TEST_PG_PORT"],
        "TEST": {"NAME": "test_passport_skills"},
    },
}
