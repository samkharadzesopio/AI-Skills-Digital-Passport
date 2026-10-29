from uuid import uuid4

from django.test import TestCase

from .models import Student
from .repositories import StudentRepository


class StudentRepositoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student = Student.objects.create(
            external_student_id="TEST-0001",
            first_name="Test",
            last_name="Student",
            email="student@example.org",
            program="Information Technologies",
            education_level="Bachelor's",
            student_status="Active",
        )

    def setUp(self):
        self.repository = StudentRepository()

    def test_external_id_lookup_returns_complete_student_in_one_query(self):
        with self.assertNumQueries(1):
            result = self.repository.get_by_external_id(self.student.external_student_id)
            self.assertEqual(result, self.student)
            self.assertEqual(result.program, self.student.program)
            self.assertEqual(result.email, self.student.email)

    def test_nonexistent_external_id_returns_none_in_one_query(self):
        with self.assertNumQueries(1):
            self.assertIsNone(self.repository.get_by_external_id("MISSING"))

    def test_external_ids_are_not_trimmed_or_case_folded(self):
        for value in ("test-0001", " TEST-0001", "TEST-0001 "):
            with self.subTest(value=value), self.assertNumQueries(2):
                self.assertIsNone(self.repository.get_by_external_id(value))
                self.assertIs(self.repository.exists_by_external_id(value), False)

    def test_exists_returns_boolean_in_one_query(self):
        for value, expected in (("TEST-0001", True), ("MISSING", False)):
            with self.subTest(value=value), self.assertNumQueries(1):
                self.assertIs(self.repository.exists_by_external_id(value), expected)

    def test_invalid_external_id_types_do_not_query_or_coerce(self):
        for value in (None, "", 123, True, uuid4(), [], {}):
            with self.subTest(value=value), self.assertNumQueries(0):
                self.assertIsNone(self.repository.get_by_external_id(value))
                self.assertIs(self.repository.exists_by_external_id(value), False)

    def test_internal_id_accepts_uuid_and_standard_string_forms(self):
        for value in (self.student.pk, str(self.student.pk), self.student.pk.hex,
                      str(self.student.pk).upper()):
            with self.subTest(value=value), self.assertNumQueries(1):
                self.assertEqual(self.repository.get_by_id(value), self.student)

    def test_nonexistent_internal_id_returns_none_in_one_query(self):
        with self.assertNumQueries(1):
            self.assertIsNone(self.repository.get_by_id(uuid4()))

    def test_malformed_internal_ids_return_none_without_queries(self):
        for value in (None, "", "not-a-uuid", "TEST-0001", 123, True, [], {}):
            with self.subTest(value=value), self.assertNumQueries(0):
                self.assertIsNone(self.repository.get_by_id(value))

    def test_internal_and_external_identifiers_are_not_interchangeable(self):
        with self.assertNumQueries(1):
            self.assertIsNone(self.repository.get_by_external_id(str(self.student.pk)))
        with self.assertNumQueries(0):
            self.assertIsNone(self.repository.get_by_id(self.student.external_student_id))
