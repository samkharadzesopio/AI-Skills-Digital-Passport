
from django.test import SimpleTestCase

from .validators import (
    ImportValidationError,
    validate_completion_record,
)


class ImportValidatorSecurityTests(SimpleTestCase):

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

    def test_valid_completion(self):
        result = validate_completion_record(
            self.record
        )
        self.assertEqual(result["grade"], 92)

    def test_nan_grade_rejected(self):
        with self.assertRaises(ImportValidationError):
            validate_completion_record({
                **self.record,
                "grade": float("nan"),
            })

    def test_infinite_grade_rejected(self):
        with self.assertRaises(ImportValidationError):
            validate_completion_record({
                **self.record,
                "grade": float("inf"),
            })

    def test_missing_student_identifier_rejected(self):
        with self.assertRaises(ImportValidationError):
            validate_completion_record({
                **self.record,
                "external_student_id": None,
            })

    def test_future_completion_rejected(self):
        with self.assertRaises(ImportValidationError):
            validate_completion_record({
                **self.record,
                "completion_date": "2099-01-01",
            })

    def test_failed_course_rejected(self):
        with self.assertRaises(ImportValidationError):
            validate_completion_record({
                **self.record,
                "passed": False,
            })
