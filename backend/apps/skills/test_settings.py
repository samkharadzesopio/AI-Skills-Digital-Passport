"""Isolated catalog tests, including Student regressions when requested."""

SECRET_KEY = "skill-model-tests-only"
INSTALLED_APPS = ["apps.students.apps.StudentsConfig", "apps.skills.apps.SkillsConfig"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}
