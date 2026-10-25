
from unittest.mock import Mock
from django.test import SimpleTestCase

from .google_sheets import read_google_sheet


class GoogleSheetsTests(SimpleTestCase):

    def test_valid_google_sheet(self):
        worksheet = Mock()

        worksheet.get.return_value = [
            [
                "external_student_id",
                "course_id",
                "completion_status",
                "grade",
                "passed",
                "completion_date",
                "source_event_id",
            ],
            [
                "BTU-T-0010",
                "AI-101",
                "completed",
                "92",
                "TRUE",
                "2026-06-15",
                "SHEET-001",
            ],
        ]

        spreadsheet = Mock()
        spreadsheet.worksheet.return_value = worksheet

        client = Mock()
        client.open_by_key.return_value = spreadsheet

        records, errors = read_google_sheet(
            spreadsheet_id="example-sheet-id-123",
            client=client,
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(errors, [])
        self.assertEqual(
            records[0]["course_id"], "AI-101"
        )
        self.assertEqual(records[0]["grade"], 92.0)
        self.assertTrue(records[0]["passed"])

    def test_invalid_completion_is_rejected(self):
        worksheet = Mock()

        worksheet.get.return_value = [
            [
                "external_student_id",
                "course_id",
                "completion_status",
                "grade",
                "passed",
                "completion_date",
                "source_event_id",
            ],
            [
                "BTU-T-0010",
                "AI-101",
                "completed",
                "40",
                "FALSE",
                "2026-06-15",
                "SHEET-002",
            ],
        ]

        client = Mock()
        client.open_by_key.return_value.worksheet.return_value = (
            worksheet
        )

        records, errors = read_google_sheet(
            "example-sheet-id-123",
            client=client,
        )

        self.assertEqual(records, [])
        self.assertEqual(len(errors), 1)
