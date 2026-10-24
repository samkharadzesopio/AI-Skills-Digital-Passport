
from io import BytesIO

from django.test import SimpleTestCase
from openpyxl import Workbook

from .excel import read_excel_completions


class ExcelImportTests(SimpleTestCase):

    def test_valid_excel_completion(self):
        workbook = Workbook()
        sheet = workbook.active

        sheet.append([
            "external_student_id",
            "course_id",
            "completion_status",
            "grade",
            "passed",
            "completion_date",
            "source_event_id",
        ])

        sheet.append([
            "BTU-T-0010",
            "AI-101",
            "completed",
            92,
            True,
            "2026-06-15",
            "SHEET-001",
        ])

        file = BytesIO()
        workbook.save(file)
        file.seek(0)

        records, errors = read_excel_completions(file)

        self.assertEqual(len(records), 1)
        self.assertEqual(errors, [])
        self.assertEqual(
            records[0]["course_id"], "AI-101"
        )
