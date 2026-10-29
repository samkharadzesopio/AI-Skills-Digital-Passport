from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.authorization import get_authenticated_student_id

from .permissions import StudentProfileAccessPending
from .repositories import StudentRepository
from .serializers import StudentProfileSerializer


class StudentProfileView(APIView):
    permission_classes = [StudentProfileAccessPending]
    http_method_names = ["get", "head", "options"]

    def get(self, request, student_id):
        linked_student_id = get_authenticated_student_id(request.user)
        student = StudentRepository().get_by_id(linked_student_id)
        if student is not None and student.external_student_id != student_id:
            student = None
        if student is None:
            raise NotFound("Student not found.")
        self.check_object_permissions(request, student)
        return Response(StudentProfileSerializer(student).data)
