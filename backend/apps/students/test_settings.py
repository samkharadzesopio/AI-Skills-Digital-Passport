"""Isolated model tests: python manage.py test apps.students --settings=apps.students.test_settings."""

import secrets

SECRET_KEY = secrets.token_urlsafe(48)
INSTALLED_APPS = ["apps.students.apps.StudentsConfig"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}
