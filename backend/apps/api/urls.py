from django.urls import path
from .views import StudentView, AdminStudents, AdminCredentials, AdminIssue, AdminRevoke, AdminPassports, AdminStatistics

urlpatterns = [
    path('student/dashboard/', StudentView.as_view(resource='dashboard')),
    path('student/skills/', StudentView.as_view(resource='skills')),
    path('student/achievements/', StudentView.as_view(resource='achievements')),
    path('student/credentials/', StudentView.as_view(resource='credentials')),
    path('student/credentials/<uuid:id>/', StudentView.as_view(resource='credentials')),
    path('student/passport/', StudentView.as_view(resource='passport')),
    path('student/passport/versions/', StudentView.as_view(resource='versions')),
    path('student/passport/versions/<uuid:id>/', StudentView.as_view(resource='versions')),
    path('admin/students/', AdminStudents.as_view()),
    path('admin/students/<uuid:id>/', AdminStudents.as_view()),
    path('admin/credentials/', AdminCredentials.as_view()),
    path('admin/credentials/issue/', AdminIssue.as_view()),
    path('admin/credentials/<uuid:id>/', AdminCredentials.as_view()),
    path('admin/credentials/<uuid:id>/revoke/', AdminRevoke.as_view()),
    path('admin/passports/', AdminPassports.as_view()),
    path('admin/passports/<uuid:id>/', AdminPassports.as_view()),
    path('admin/passports/<uuid:id>/versions/', AdminPassports.as_view(), {'versions': True}),
    path('admin/statistics/', AdminStatistics.as_view()),
]
