from uuid import uuid4

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from .models import Skill
from .repositories import SkillRepository


class SkillRepositoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.skill = Skill.objects.create(
            skill_code="SKL-001", skill_name="AI Literacy", category="AI Skill",
            description="Fundamentals of AI capabilities.",
            stamp_type=Skill.StampType.FOCUSED, badge_asset_id="BDG-AI-001",
        )

    def setUp(self):
        self.repository = SkillRepository()

    def test_code_lookup_returns_complete_skill_in_one_query(self):
        with self.assertNumQueries(1):
            result = self.repository.get_by_code(self.skill.skill_code)
            self.assertIsInstance(result, Skill)
            self.assertEqual(result, self.skill)
            self.assertEqual(result.description, self.skill.description)
            self.assertEqual(result.stamp_type, self.skill.stamp_type)

    def test_unknown_code_returns_none_in_one_query(self):
        with self.assertNumQueries(1):
            self.assertIsNone(self.repository.get_by_code("MISSING"))

    def test_codes_are_not_trimmed_or_case_folded(self):
        for value in ("skl-001", " SKL-001", "SKL-001 "):
            with self.subTest(value=value), self.assertNumQueries(2):
                self.assertIsNone(self.repository.get_by_code(value))
                self.assertIs(self.repository.exists_by_code(value), False)

    def test_exists_returns_boolean_in_one_query(self):
        for value, expected in (("SKL-001", True), ("MISSING", False)):
            with self.subTest(value=value), self.assertNumQueries(1):
                self.assertIs(self.repository.exists_by_code(value), expected)

    def test_invalid_code_types_do_not_query_or_coerce(self):
        for value in (None, "", 123, True, uuid4(), [], {}):
            with self.subTest(value=value), self.assertNumQueries(0):
                self.assertIsNone(self.repository.get_by_code(value))
                self.assertIs(self.repository.exists_by_code(value), False)

    def test_uuid_lookup_accepts_uuid_and_standard_string_forms(self):
        for value in (self.skill.pk, str(self.skill.pk), self.skill.pk.hex,
                      str(self.skill.pk).upper()):
            with self.subTest(value=value), self.assertNumQueries(1):
                result = self.repository.get_by_id(value)
                self.assertIsInstance(result, Skill)
                self.assertEqual(result, self.skill)

    def test_unknown_uuid_returns_none_in_one_query(self):
        with self.assertNumQueries(1):
            self.assertIsNone(self.repository.get_by_id(uuid4()))

    def test_invalid_uuid_returns_none_without_queries(self):
        for value in (None, "", "not-a-uuid", "SKL-001", 123, True, [], {}):
            with self.subTest(value=value), self.assertNumQueries(0):
                self.assertIsNone(self.repository.get_by_id(value))

    def test_internal_ids_and_codes_are_not_interchangeable(self):
        with self.assertNumQueries(1):
            self.assertIsNone(self.repository.get_by_code(str(self.skill.pk)))
        with self.assertNumQueries(0):
            self.assertIsNone(self.repository.get_by_id(self.skill.skill_code))

    def test_lookups_do_not_write_or_lock_records(self):
        original = list(Skill.objects.values())
        with CaptureQueriesContext(connection) as queries:
            self.repository.get_by_code("SKL-001")
            self.repository.get_by_code("MISSING")
            self.repository.get_by_id(self.skill.pk)
            self.repository.get_by_id(uuid4())
            self.repository.exists_by_code("SKL-001")
            self.repository.exists_by_code("MISSING")
        self.assertEqual(len(queries), 6)
        for query in queries:
            self.assertTrue(query["sql"].lstrip().upper().startswith("SELECT"))
            self.assertNotIn("FOR UPDATE", query["sql"].upper())
        self.assertEqual(list(Skill.objects.values()), original)
