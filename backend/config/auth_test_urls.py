"""Extra routes used only by the isolated accounts regression suite."""

from django.urls import include, path
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.identity import authorized_student_id
from apps.accounts.permissions import IsStudent


class PrivateIdentityProbe(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        return Response({"student_uuid": str(authorized_student_id(request.user))})


urlpatterns = [
    path("accounts/", include("apps.accounts.urls")),
    path("private/", PrivateIdentityProbe.as_view()),
    path("api/students/", include("apps.students.urls")),
    path("api/integrations/", include("apps.integrations.urls")),
    path("api/verification/", include("apps.verification.urls")),
]
