from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase

from .models import Student
from .tests import StudentDataMixin


class StudentNormalizationTests(StudentDataMixin, TestCase):
    def test_save_trims_whitespace_and_preserves_case_and_uuid(self):
        student = Student(**self.student_data(external_student_id=" \tTest-0001\r\n"))
        original_id = student.pk
        student.save()
        student.refresh_from_db()
        self.assertEqual(student.external_student_id, "Test-0001")
        self.assertEqual(student.pk, original_id)
        student.external_student_id = " Test-0002 "
        student.save(update_fields=["external_student_id"])
        student.refresh_from_db()
        self.assertEqual(student.external_student_id, "Test-0002")
        self.assertEqual(student.pk, original_id)

    def test_full_clean_normalizes_before_length_and_uniqueness_validation(self):
        student = Student(**self.student_data(external_student_id=" " + "X" * 120 + " "))
        student.full_clean()
        student.save()
        duplicate = Student(**self.student_data(
            external_student_id="\t" + "X" * 120 + "\n", email="other@example.org",
        ))
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_normalized_duplicate_is_rejected_and_case_is_not_folded(self):
        Student.objects.create(**self.student_data())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Student.objects.create(**self.student_data(
                external_student_id=" TEST-0001 ", email="duplicate@example.org",
            ))
        Student.objects.create(**self.student_data(
            external_student_id="test-0001", email="lower@example.org",
        ))
        self.assertEqual(Student.objects.count(), 2)

    def test_bulk_insert_cannot_bypass_canonical_identifier_constraint(self):
        for value in (
            " TEST-0001", "TEST-0001 ", "\tTEST-0001", "TEST-0001\n", "\r\n",
            "\u00a0TEST-0001", "TEST-0001\u2003", "\u3000TEST-0001", "TEST-0001\x1c",
        ):
            with self.subTest(value=value), self.assertRaises(IntegrityError), transaction.atomic():
                Student.objects.bulk_create([Student(**self.student_data(external_student_id=value))])

    def test_unicode_whitespace_is_normalized_before_save(self):
        student = Student.objects.create(**self.student_data(
            external_student_id="\u00a0\u3000Test-0001\u2003\x1c",
        ))
        student.refresh_from_db()
        self.assertEqual(student.external_student_id, "Test-0001")

    def test_queryset_and_raw_updates_cannot_store_surrounding_whitespace(self):
        student = Student.objects.create(**self.student_data())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Student.objects.filter(pk=student.pk).update(external_student_id=" TEST-0001 ")
        with self.assertRaises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("UPDATE students SET external_student_id = %s WHERE id = %s", [
                    "\tTEST-0001", student.pk,
                ])
        student.refresh_from_db()
        self.assertEqual(student.external_student_id, "TEST-0001")
