from types import SimpleNamespace
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Student
from .permissions import StudentProfileAccessPending
from .repositories import StudentRepository
from .serializers import StudentProfileSerializer


@override_settings(ROOT_URLCONF="apps.students.test_urls")
class StudentProfileAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = Student.objects.create(
            external_student_id="TEST-0001", first_name="Test", last_name="Student",
            email="student@example.org", program="Information Technologies",
            education_level="Bachelor's", student_status="Active",
        )

    def profile_url(self, student_id="TEST-0001"):
        return reverse("students:student-profile", kwargs={"student_id": student_id})

    def test_anonymous_access_is_denied_before_lookup(self):
        with patch.object(StudentRepository, "get_by_external_id") as lookup:
            for student_id in ("TEST-0001", "MISSING"):
                with self.subTest(student_id=student_id), self.assertNumQueries(0):
                    response = self.client.get(self.profile_url(student_id))
                    self.assertEqual(response.status_code, 403)
                    self.assertNotIn("email", response.data)
            lookup.assert_not_called()

    def test_authentication_alone_does_not_grant_access(self):
        self.client.force_authenticate(user=SimpleNamespace(is_authenticated=True))
        with self.assertNumQueries(0):
            response = self.client.get(self.profile_url())
        self.assertEqual(response.status_code, 403)

    # These tests bypass only the pending permission in-process. No production
    # setting, account, header, or request parameter can enable this bypass.
    @patch.object(StudentProfileAccessPending, "has_permission", return_value=True)
    def test_permitted_retrieval_uses_repository_and_exact_response_fields(self, permission):
        with patch.object(
            StudentRepository, "get_by_external_id",
            wraps=StudentRepository().get_by_external_id,
        ) as lookup, self.assertNumQueries(1):
            response = self.client.get(self.profile_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {
            "student_id": "TEST-0001", "first_name": "Test", "last_name": "Student",
            "email": "student@example.org", "program": "Information Technologies",
            "education_level": "Bachelor's", "student_status": "Active",
        })
        lookup.assert_called_once_with("TEST-0001")

    @patch.object(StudentProfileAccessPending, "has_permission", return_value=True)
    def test_permitted_missing_student_returns_404(self, permission):
        with self.assertNumQueries(1):
            response = self.client.get(self.profile_url("MISSING"))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data, {"detail": "Student not found."})

    @patch.object(StudentProfileAccessPending, "has_permission", return_value=True)
    def test_external_identifier_is_not_case_folded(self, permission):
        self.assertEqual(self.client.get(self.profile_url("test-0001")).status_code, 404)

    @patch.object(StudentProfileAccessPending, "has_permission", return_value=True)
    def test_mutating_methods_are_not_supported(self, permission):
        original = StudentProfileSerializer(self.student).data
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method), self.assertNumQueries(0):
                response = getattr(self.client, method)(
                    self.profile_url(), {"first_name": "Changed"}, format="json",
                )
                self.assertEqual(response.status_code, 405)
        self.student.refresh_from_db()
        self.assertEqual(StudentProfileSerializer(self.student).data, original)

    def test_serializer_fields_are_all_read_only(self):
        serializer = StudentProfileSerializer()
        self.assertTrue(all(field.read_only for field in serializer.fields.values()))

    @patch.object(StudentProfileAccessPending, "has_permission", return_value=True)
    @patch.object(StudentProfileAccessPending, "has_object_permission", return_value=False)
    def test_object_permission_is_checked_before_serialization(self, object_permission, permission):
        response = self.client.get(self.profile_url())
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("email", response.data)
        object_permission.assert_called_once()
