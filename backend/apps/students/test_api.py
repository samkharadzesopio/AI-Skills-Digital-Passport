from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import User

from .models import Student
from .repositories import StudentRepository
from .serializers import StudentProfileSerializer


@override_settings(ROOT_URLCONF="apps.students.test_urls")
class StudentProfileAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = Student.objects.create(
            external_student_id="TEST-0001", first_name="Test", last_name="Student",
            email="student@btu.edu.ge", program="Information Technologies",
            education_level="Bachelor's", student_status="Active",
        )

    def setUp(self):
        self.user = User.objects.create_user(
            email="student@btu.edu.ge",
            password="Strong-Test-Passphrase!2026",
            student=self.student,
            is_email_verified=True,
        )
        # Simulate the user loaded through StudentOTPBackend's joined database read.
        self.user._accounts_identity_authoritative = True

    def profile_url(self, student_id="TEST-0001"):
        return reverse("students:student-profile", kwargs={"student_id": student_id})

    def test_anonymous_access_is_denied_before_lookup(self):
        with self.assertNumQueries(0):
            response = self.client.get(self.profile_url())
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("email", response.data)

    def test_authentication_without_a_student_link_is_denied(self):
        unlinked = User.objects.create_user(
            email="unlinked@btu.edu.ge",
            password="Strong-Test-Passphrase!2026",
            is_email_verified=True,
        )
        self.client.force_authenticate(user=unlinked)
        with self.assertNumQueries(0):
            response = self.client.get(self.profile_url())
        self.assertEqual(response.status_code, 403)

    def test_permitted_retrieval_returns_only_the_linked_profile(self):
        self.client.force_authenticate(user=self.user)
        with self.assertNumQueries(1):
            response = self.client.get(self.profile_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {
            "student_id": "TEST-0001", "first_name": "Test", "last_name": "Student",
            "email": "student@btu.edu.ge", "program": "Information Technologies",
            "education_level": "Bachelor's", "student_status": "Active",
        })

    def test_student_b_gets_not_found_for_another_students_external_id_or_uuid(self):
        other = Student.objects.create(
            external_student_id="TEST-0002", first_name="Other", last_name="Student",
            email="other@example.org", program="Information Technologies",
            education_level="Bachelor's", student_status="Active",
        )
        self.client.force_authenticate(user=self.user)
        for identifier in (other.external_student_id, str(other.pk), "MISSING"):
            authenticated = User.objects.select_related("student").get(pk=self.user.pk)
            authenticated._accounts_identity_authoritative = True
            self.client.force_authenticate(user=authenticated)
            with self.subTest(identifier=identifier), self.assertNumQueries(1):
                response = self.client.get(self.profile_url(identifier))
            self.assertEqual(response.status_code, 404)
            self.assertNotIn("email", response.data)

    def test_mutating_methods_are_not_supported(self):
        self.client.force_authenticate(user=self.user)
        original = StudentProfileSerializer(self.student).data
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self.profile_url(), {"first_name": "Changed"}, format="json",
                )
                self.assertEqual(response.status_code, 405)
        self.student.refresh_from_db()
        self.assertEqual(StudentProfileSerializer(self.student).data, original)

    def test_serializer_fields_are_read_only(self):
        serializer = StudentProfileSerializer()
        self.assertTrue(all(field.read_only for field in serializer.fields.values()))
