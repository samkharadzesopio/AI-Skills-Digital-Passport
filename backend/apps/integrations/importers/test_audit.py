
from django.test import SimpleTestCase

from .audit import InMemoryImportAudit


class ImportAuditTests(SimpleTestCase):

    def setUp(self):
        self.audit = InMemoryImportAudit()

    def test_successful_import(self):
        entry = self.audit.record(
            "BTU_GOOGLE_SHEETS",
            {
                "processed": 2,
                "awarded": 2,
                "skipped": 0,
                "failed": 0,
                "errors": [],
            },
        )

        self.assertEqual(
            entry["status"], "COMPLETED"
        )
        self.assertEqual(entry["awarded"], 2)

    def test_partial_import(self):
        entry = self.audit.record(
            "BTU_EXCEL",
            {
                "processed": 3,
                "awarded": 1,
                "skipped": 0,
                "failed": 2,
                "errors": [
                    {"row": 2, "error": "Invalid grade"},
                    {"row": 3, "error": "Missing student"},
                ],
            },
        )

        self.assertEqual(
            entry["status"], "PARTIAL"
        )
        self.assertEqual(entry["error_count"], 2)

    def test_failed_import(self):
        entry = self.audit.record(
            "BTU_EXCEL",
            {
                "processed": 1,
                "awarded": 0,
                "skipped": 0,
                "failed": 1,
                "errors": [{"row": 2, "error": "Invalid"}],
            },
        )

        self.assertEqual(entry["status"], "FAILED")

    def test_history_newest_first(self):
        self.audit.record(
            "BTU_EXCEL",
            {
                "processed": 1,
                "awarded": 1,
                "skipped": 0,
                "failed": 0,
                "errors": [],
            },
        )

        latest = self.audit.record(
            "BTU_GOOGLE_SHEETS",
            {
                "processed": 1,
                "awarded": 0,
                "skipped": 1,
                "failed": 0,
                "errors": [],
            },
        )

        history = self.audit.list_history()

        self.assertEqual(len(history), 2)
        self.assertEqual(
            history[0]["id"], latest["id"]
        )

    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError):
            self.audit.record(
                "UNTRUSTED_SOURCE",
                {
                    "processed": 0,
                    "awarded": 0,
                    "skipped": 0,
                    "failed": 0,
                    "errors": [],
                },
            )
