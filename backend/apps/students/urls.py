from django.urls import path

from .views import StudentProfileView

app_name = "students"

urlpatterns = [
    path("students/<str:student_id>/", StudentProfileView.as_view(), name="student-profile"),
]
