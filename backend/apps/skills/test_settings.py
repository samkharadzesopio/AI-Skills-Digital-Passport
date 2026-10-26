"""Isolated catalog tests, including Student regressions when requested."""

import secrets

SECRET_KEY = secrets.token_urlsafe(48)
INSTALLED_APPS = ["apps.students.apps.StudentsConfig", "apps.skills.apps.SkillsConfig"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}
