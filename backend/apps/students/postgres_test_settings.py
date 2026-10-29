"""Opt-in tests for a disposable, explicitly supplied PostgreSQL cluster."""

import os

from .test_settings import *  # noqa: F403

# No host/port defaults: never accidentally target a normal local service.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "postgres",
        "USER": "passport_test",
        "HOST": os.environ["STUDENT_TEST_PG_HOST"],
        "PORT": os.environ["STUDENT_TEST_PG_PORT"],
        "TEST": {"NAME": "test_passport_students"},
    },
}
