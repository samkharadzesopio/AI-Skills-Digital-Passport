"""App-local routing for integration tests; shared project URLs stay unchanged."""

from django.urls import include, path

urlpatterns = [path("api/v1/", include("apps.students.urls"))]
