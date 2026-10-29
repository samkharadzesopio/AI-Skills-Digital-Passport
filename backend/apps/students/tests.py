import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from unittest import skipUnless

from django.core.exceptions import ValidationError
from django.db import IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from .models import Student


class StudentDataMixin:
    def student_data(self, **overrides):
        data = {
            "external_student_id": "TEST-0001",
            "first_name": "Test",
            "last_name": "Student",
            "email": "student@example.org",
            "program": "Information Technologies",
            "education_level": "Bachelor's",
            "student_status": "Active",
        }
        return data | overrides


class StudentModelTests(StudentDataMixin, TestCase):
    def assert_database_rejects(self, **overrides):
        # Bypass full_clean() to prove the database enforces the constraint.
        with self.assertRaises(IntegrityError), transaction.atomic():
            Student.objects.create(**self.student_data(**overrides))

    def test_valid_profile_and_distinct_uuid_defaults(self):
        student = Student(**self.student_data())
        student.full_clean()
        student.save()
        student.refresh_from_db()
        self.assertIsInstance(student.pk, uuid.UUID)
        self.assertNotEqual(student.pk, Student().pk)
        self.assertEqual(student.program, "Information Technologies")
        self.assertEqual(str(student), "TEST-0001")
        self.assertEqual(Student._meta.db_table, "students")
        self.assertIsNotNone(student.created_at)
        self.assertIsNotNone(student.updated_at)
        self.assertTrue(timezone.is_aware(student.created_at))

    def test_external_identifier_is_unique(self):
        Student.objects.create(**self.student_data())
        self.assert_database_rejects(email="other@example.org")

    def test_email_is_unique_ignoring_case(self):
        Student.objects.create(**self.student_data())
        for email in ("student@example.org", "STUDENT@EXAMPLE.ORG"):
            with self.subTest(email=email):
                self.assert_database_rejects(external_student_id="TEST-0002", email=email)

    def test_nonblank_text_is_enforced_by_database(self):
        for field in (
            "external_student_id", "first_name", "last_name",
            "program", "education_level", "student_status",
        ):
            for value in ("", "   "):
                with self.subTest(field=field, value=value):
                    self.assert_database_rejects(**{field: value})

    def test_required_fields_reject_null_at_database(self):
        for field in self.student_data():
            with self.subTest(field=field):
                self.assert_database_rejects(**{field: None})

    def test_email_shape_and_whitespace_are_enforced_by_database(self):
        for email in (
            "", "   ", "not-an-email", "student@example", "a@@example.org",
            " student@example.org", "student@example.org ", "a b@example.org",
        ):
            with self.subTest(email=email):
                self.assert_database_rejects(email=email)

    def test_model_validation_reports_required_and_invalid_fields(self):
        for field in self.student_data():
            with self.subTest(field=field):
                student = Student(**self.student_data(**{field: ""}))
                with self.assertRaises(ValidationError) as caught:
                    student.full_clean()
                self.assertIn(field, caught.exception.message_dict)
        with self.assertRaises(ValidationError):
            Student(**self.student_data(email="not-an-email")).full_clean()

    def test_model_validation_enforces_field_lengths(self):
        for field in self.student_data():
            limit = Student._meta.get_field(field).max_length
            with self.subTest(field=field), self.assertRaises(ValidationError):
                Student(**self.student_data(**{field: "x" * (limit + 1)})).full_clean()

    def test_full_clean_detects_case_insensitive_email_collision(self):
        Student.objects.create(**self.student_data())
        student = Student(**self.student_data(
            external_student_id="TEST-0002", email="STUDENT@EXAMPLE.ORG",
        ))
        with self.assertRaises(ValidationError):
            student.full_clean()

    def test_save_updates_timestamp_without_changing_creation_time(self):
        student = Student.objects.create(**self.student_data())
        created_at = student.created_at
        earlier = timezone.now() - timedelta(days=1)
        Student.objects.filter(pk=student.pk).update(updated_at=earlier)
        student.first_name = "Updated"
        student.save()
        student.refresh_from_db()
        self.assertEqual(student.created_at, created_at)
        self.assertGreater(student.updated_at, earlier)

    def test_duplicate_names_are_allowed_for_distinct_students(self):
        Student.objects.create(**self.student_data())
        Student.objects.create(**self.student_data(
            external_student_id="TEST-0002", email="another@example.org",
        ))
        self.assertEqual(Student.objects.count(), 2)


@skipUnless(connection.vendor == "postgresql", "Requires isolated PostgreSQL")
class StudentPostgreSQLTests(StudentDataMixin, TransactionTestCase):
    def test_raw_insert_uses_server_uuid_and_timestamp_defaults(self):
        data = self.student_data()
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO students (external_student_id, first_name, last_name, "
                "email, program, education_level, student_status) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id, created_at, updated_at",
                list(data.values()),
            )
            student_id, created_at, updated_at = cursor.fetchone()
        self.assertIsInstance(student_id, uuid.UUID)
        self.assertEqual(student_id.version, 4)
        self.assertIsNotNone(created_at)
        self.assertIsNotNone(updated_at)

    def test_raw_and_queryset_updates_refresh_timestamp(self):
        student = Student.objects.create(**self.student_data())
        original = student.updated_at
        with connection.cursor() as cursor:
            cursor.execute("UPDATE students SET first_name = %s WHERE id = %s", ["Raw", student.pk])
        student.refresh_from_db()
        self.assertGreater(student.updated_at, original)
        previous = student.updated_at
        Student.objects.filter(pk=student.pk).update(first_name="Bulk")
        student.refresh_from_db()
        self.assertGreater(student.updated_at, previous)

    def test_postgresql_enforces_varchar_lengths(self):
        from django.db import DataError

        for field in self.student_data():
            with self.subTest(field=field), self.assertRaises(DataError), transaction.atomic():
                Student.objects.create(**self.student_data(**{
                    field: "x" * (Student._meta.get_field(field).max_length + 1),
                }))

    def assert_concurrent_duplicate_rejected(self, duplicate_email):
        barrier = Barrier(2)

        def create(index):
            close_old_connections()
            try:
                data = self.student_data(
                    external_student_id=f"TEST-{index}" if duplicate_email else "SAME-ID",
                    email=("STUDENT@example.org" if index else "student@example.org")
                    if duplicate_email else f"student{index}@example.org",
                )
                barrier.wait(timeout=10)
                try:
                    with transaction.atomic():
                        Student.objects.create(**data)
                    return "created"
                except IntegrityError:
                    return "duplicate"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(create, range(2)))
        self.assertCountEqual(outcomes, ["created", "duplicate"])
        self.assertEqual(Student.objects.count(), 1)

    def test_concurrent_external_id_uniqueness(self):
        self.assert_concurrent_duplicate_rejected(duplicate_email=False)

    def test_concurrent_case_insensitive_email_uniqueness(self):
        self.assert_concurrent_duplicate_rejected(duplicate_email=True)

    def test_reference_schema_matches_migration_and_preserves_foreign_keys(self):
        schema_sql = (Path(__file__).resolve().parents[2] / "database" / "schema.sql").read_text()
        # Execute the complete reference only in a separate schema in the test DB.
        schema_sql = schema_sql.removeprefix("\ufeff").strip()
        self.assertTrue(schema_sql.endswith("COMMIT;"))
        schema_sql = schema_sql.replace("BEGIN;", "", 1).removesuffix("COMMIT;")
        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA student_reference_test")
            try:
                with transaction.atomic():
                    cursor.execute("SET LOCAL search_path TO student_reference_test, public")
                    cursor.execute(schema_sql)

                def columns(schema):
                    cursor.execute(
                        "SELECT column_name, data_type, character_maximum_length, is_nullable "
                        "FROM information_schema.columns WHERE table_schema = %s "
                        "AND table_name = 'students' ORDER BY column_name", [schema],
                    )
                    return cursor.fetchall()

                self.assertEqual(columns("public"), columns("student_reference_test"))

                def defaults(schema):
                    cursor.execute(
                        "SELECT column_name, column_default FROM information_schema.columns "
                        "WHERE table_schema = %s AND table_name = 'students' "
                        "AND column_default IS NOT NULL ORDER BY column_name", [schema],
                    )
                    return cursor.fetchall()

                self.assertEqual(defaults("public"), defaults("student_reference_test"))

                def constraints(schema):
                    cursor.execute(
                        "SELECT conname, contype FROM pg_constraint "
                        "WHERE conrelid = %s::regclass ORDER BY conname", [f"{schema}.students"],
                    )
                    return cursor.fetchall()

                self.assertEqual(constraints("public"), constraints("student_reference_test"))

                def indexes(schema):
                    cursor.execute(
                        "SELECT indexname FROM pg_indexes WHERE schemaname = %s "
                        "AND tablename = 'students' ORDER BY indexname", [schema],
                    )
                    return cursor.fetchall()

                self.assertEqual(indexes("public"), indexes("student_reference_test"))
                for schema in ("public", "student_reference_test"):
                    cursor.execute(
                        "SELECT tgname, p.proname FROM pg_trigger t "
                        "JOIN pg_proc p ON p.oid = t.tgfoid "
                        "WHERE tgrelid = %s::regclass AND NOT tgisinternal",
                        [f"{schema}.students"],
                    )
                    self.assertEqual(cursor.fetchall(), [
                        ("trg_students_updated_at", "students_set_updated_at"),
                    ])
                cursor.execute(
                    "SELECT count(*) FROM pg_constraint WHERE contype = 'f' "
                    "AND confrelid = 'student_reference_test.students'::regclass"
                )
                self.assertEqual(cursor.fetchone()[0], 2)
            finally:
                cursor.execute("DROP SCHEMA student_reference_test CASCADE")
