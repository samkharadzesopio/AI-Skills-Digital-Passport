
from unittest.mock import Mock

from django.test import SimpleTestCase

from .service import process_completion_import


class ImportServiceTests(SimpleTestCase):

    def setUp(self):
        self.record = {
            "external_student_id": "BTU-T-0010",
            "course_id": "AI-101",
            "completion_status": "completed",
            "grade": 92,
            "passed": True,
            "completion_date": "2026-06-15",
            "source_event_id": "SHEET-001",
        }

    def test_valid_course_awards_skills(self):
        award = Mock(
            return_value=([object(), object()], True)
        )

        result = process_completion_import(
            [self.record],
            source="BTU_GOOGLE_SHEETS",
            award_func=award,
        )

        self.assertEqual(result["awarded"], 2)
        self.assertEqual(result["failed"], 0)

        self.assertEqual(
            award.call_args.kwargs["approved_skill_codes"],
            ["AI_LITERACY", "AI_FUNDAMENTALS"],
        )

        self.assertEqual(
            award.call_args.kwargs["source"],
            "BTU_GOOGLE_SHEETS",
        )

    def test_repeated_event_is_skipped(self):
        award = Mock(return_value=([], False))

        result = process_completion_import(
            [self.record],
            source="BTU_EXCEL",
            award_func=award,
        )

        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["awarded"], 0)

    def test_failed_course_is_rejected(self):
        award = Mock()
        failed_record = {
            **self.record,
            "grade": 40,
        }

        result = process_completion_import(
            [failed_record],
            source="BTU_EXCEL",
            award_func=award,
        )

        self.assertEqual(result["failed"], 1)
        award.assert_not_called()
