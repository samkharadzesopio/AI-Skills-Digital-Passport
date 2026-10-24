import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from unittest import skipUnless

from django.core.exceptions import ValidationError
from django.db import DataError, IntegrityError, close_old_connections, connection, transaction
from django.test import TestCase, TransactionTestCase

from .models import Skill


class SkillDataMixin:
    def skill_data(self, **overrides):
        return {
            "skill_code": "SKL-001", "skill_name": "AI Literacy",
            "category": "AI Skill", "description": "Fundamentals of AI capabilities.",
            "stamp_type": Skill.StampType.FOCUSED, "badge_asset_id": "BDG-AI-001",
        } | overrides


class SkillModelTests(SkillDataMixin, TestCase):
    def test_valid_catalog_entry(self):
        skill = Skill(**self.skill_data())
        skill.full_clean()
        skill.save()
        skill.refresh_from_db()
        self.assertIsInstance(skill.pk, uuid.UUID)
        self.assertNotEqual(skill.pk, Skill().pk)
        self.assertEqual(Skill._meta.db_table, "skills_catalog")
        self.assertEqual(str(skill), "SKL-001")
        self.assertIsNotNone(skill.created_at)
        self.assertIsNotNone(skill.updated_at)

    def test_skill_code_is_unique_at_database(self):
        Skill.objects.create(**self.skill_data())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Skill.objects.create(**self.skill_data(skill_name="Another name"))

    def test_full_clean_detects_duplicate_code(self):
        Skill.objects.create(**self.skill_data())
        with self.assertRaises(ValidationError):
            Skill(**self.skill_data()).full_clean()

    def test_nonblank_constraints_at_database(self):
        for field in ("skill_code", "skill_name", "category", "description", "badge_asset_id"):
            for value in ("", "   "):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(IntegrityError), transaction.atomic():
                        Skill.objects.create(**self.skill_data(**{field: value}))

    def test_required_fields_reject_null_at_database(self):
        for field in self.skill_data():
            with self.subTest(field=field):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    Skill.objects.create(**self.skill_data(**{field: None}))

    def test_stamp_type_constraint_at_database(self):
        for value in ("", " ", "OTHER", "focused"):
            with self.subTest(value=value):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    Skill.objects.create(**self.skill_data(stamp_type=value))

    def test_all_sql_stamp_types_are_supported(self):
        for index, stamp_type in enumerate(Skill.StampType.values):
            with self.subTest(stamp_type=stamp_type):
                skill = Skill(**self.skill_data(skill_code=f"TEST-{index}", stamp_type=stamp_type))
                skill.full_clean()
                skill.save()

    def test_model_validation_of_required_fields_lengths_and_stamp_type(self):
        for field in self.skill_data():
            with self.subTest(field=field), self.assertRaises(ValidationError):
                Skill(**self.skill_data(**{field: ""})).full_clean()
            maximum = Skill._meta.get_field(field).max_length
            if maximum:
                with self.subTest(field=field, length=maximum + 1), self.assertRaises(ValidationError):
                    Skill(**self.skill_data(**{field: "x" * (maximum + 1)})).full_clean()
        with self.assertRaises(ValidationError):
            Skill(**self.skill_data(stamp_type="OTHER")).full_clean()

    def test_names_and_badges_can_be_shared(self):
        Skill.objects.create(**self.skill_data())
        Skill.objects.create(**self.skill_data(skill_code="SKL-002"))
        self.assertEqual(Skill.objects.count(), 2)

    def test_save_preserves_creation_timestamp(self):
        skill = Skill.objects.create(**self.skill_data())
        created_at = skill.created_at
        updated_at = skill.updated_at
        skill.description = "Updated catalog description."
        skill.save()
        skill.refresh_from_db()
        self.assertEqual(skill.created_at, created_at)
        self.assertGreaterEqual(skill.updated_at, updated_at)


@skipUnless(connection.vendor == "postgresql", "Requires isolated PostgreSQL")
class SkillPostgreSQLTests(SkillDataMixin, TransactionTestCase):
    def test_server_uuid_and_timestamp_defaults(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO skills_catalog (skill_code, skill_name, category, description, "
                "stamp_type, badge_asset_id) VALUES (%s, %s, %s, %s, %s, %s) "
                "RETURNING id, created_at, updated_at", list(self.skill_data().values()),
            )
            skill_id, created_at, updated_at = cursor.fetchone()
        self.assertEqual(skill_id.version, 4)
        self.assertIsNotNone(created_at)
        self.assertEqual(created_at, updated_at)

    def test_raw_and_bulk_updates_refresh_timestamp(self):
        skill = Skill.objects.create(**self.skill_data())
        original = skill.updated_at
        with connection.cursor() as cursor:
            cursor.execute("UPDATE skills_catalog SET description = %s WHERE id = %s", ["Raw update", skill.pk])
        skill.refresh_from_db()
        self.assertGreater(skill.updated_at, original)
        original = skill.updated_at
        Skill.objects.filter(pk=skill.pk).update(description="Bulk update")
        skill.refresh_from_db()
        self.assertGreater(skill.updated_at, original)

    def test_postgresql_enforces_varchar_lengths(self):
        for field in self.skill_data():
            maximum = Skill._meta.get_field(field).max_length
            if maximum:
                with self.subTest(field=field), self.assertRaises(DataError), transaction.atomic():
                    Skill.objects.create(**self.skill_data(**{field: "x" * (maximum + 1)}))

    def test_concurrent_duplicate_codes_create_one_record(self):
        barrier = Barrier(2)

        def create(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    with transaction.atomic():
                        Skill.objects.create(**self.skill_data())
                    return "created"
                except IntegrityError:
                    return "duplicate"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(create, range(2)))
        self.assertCountEqual(outcomes, ["created", "duplicate"])
        self.assertEqual(Skill.objects.count(), 1)

    def test_reference_schema_matches_migration(self):
        sql = (Path(__file__).resolve().parents[2] / "database" / "schema.sql").read_text().strip()
        self.assertTrue(sql.endswith("COMMIT;"))
        sql = sql.replace("BEGIN;", "", 1).removesuffix("COMMIT;")
        with connection.cursor() as cursor:
            cursor.execute("CREATE SCHEMA skill_reference_test")
            try:
                with transaction.atomic():
                    cursor.execute("SET LOCAL search_path TO skill_reference_test, public")
                    cursor.execute(sql)

                def structure(schema):
                    cursor.execute(
                        "SELECT column_name, data_type, character_maximum_length, is_nullable, column_default "
                        "FROM information_schema.columns WHERE table_schema = %s "
                        "AND table_name = 'skills_catalog' ORDER BY column_name", [schema],
                    )
                    columns = cursor.fetchall()
                    cursor.execute(
                        "SELECT conname, contype FROM pg_constraint WHERE conrelid = %s::regclass ORDER BY conname",
                        [f"{schema}.skills_catalog"],
                    )
                    constraints = cursor.fetchall()
                    cursor.execute(
                        "SELECT indexname FROM pg_indexes WHERE schemaname = %s "
                        "AND tablename = 'skills_catalog' ORDER BY indexname", [schema],
                    )
                    indexes = cursor.fetchall()
                    cursor.execute(
                        "SELECT tgname, p.proname FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid "
                        "WHERE tgrelid = %s::regclass AND NOT tgisinternal", [f"{schema}.skills_catalog"],
                    )
                    return columns, constraints, indexes, cursor.fetchall()

                self.assertEqual(structure("public"), structure("skill_reference_test"))
                cursor.execute(
                    "SELECT count(*) FROM pg_constraint WHERE contype = 'f' "
                    "AND confrelid = 'skill_reference_test.skills_catalog'::regclass"
                )
                self.assertEqual(cursor.fetchone()[0], 1)
            finally:
                cursor.execute("DROP SCHEMA skill_reference_test CASCADE")
