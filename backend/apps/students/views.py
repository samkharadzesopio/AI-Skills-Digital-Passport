from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import StudentProfileAccessPending
from .repositories import StudentRepository
from .serializers import StudentProfileSerializer


class StudentProfileView(APIView):
    permission_classes = [StudentProfileAccessPending]
    http_method_names = ["get", "head", "options"]

    def get(self, request, student_id):
        student = StudentRepository().get_by_external_id(student_id)
        if student is None:
            raise NotFound("Student not found.")
        self.check_object_permissions(request, student)
        return Response(StudentProfileSerializer(student).data)
