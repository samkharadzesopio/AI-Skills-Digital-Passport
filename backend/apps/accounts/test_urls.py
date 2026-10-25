from django.urls import include, path
from rest_framework.response import Response
from rest_framework.views import APIView
from .identity import authorized_student_id
from .permissions import IsStudent


class PrivateIdentity(APIView):
    permission_classes = [IsStudent]

    def get(self, request):
        return Response({'student_uuid': str(authorized_student_id(request.user))})


urlpatterns = [
    path('accounts/', include('apps.accounts.urls')),
    path('private/', PrivateIdentity.as_view()),
    path('students/', include('apps.students.urls')),
]
