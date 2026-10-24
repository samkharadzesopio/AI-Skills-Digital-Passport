
from django.test import SimpleTestCase
from .services import ClassroomService
from .sync import ClassroomSyncService
from .ledgers import InMemorySyncLedger


class ClassroomServiceTests(SimpleTestCase):

    def setUp(self):
        self.service = ClassroomService()

    def test_mock_completions_are_returned(self):
        records = self.service.get_completions()

        self.assertEqual(len(records), 3)

    def test_only_completed_approved_ai_courses_qualify(self):
        records = self.service.get_eligible_completions()

        self.assertEqual(len(records), 1)
        self.assertEqual(
            records[0]["course_id"],
            "AI-101"
        )

    def test_incomplete_course_is_excluded(self):
        records = self.service.get_eligible_completions()

        course_ids = [
            record["course_id"]
            for record in records
        ]

        self.assertNotIn("AI-201", course_ids)

    def test_unapproved_course_is_excluded(self):
        records = self.service.get_eligible_completions()

        course_ids = [
            record["course_id"]
            for record in records
        ]

        self.assertNotIn("MATH-101", course_ids)


class ClassroomSyncTests(SimpleTestCase):

    def setUp(self):
        self.issued_events = []

        def fake_issuer(
            student_id,
            course_id,
            source_event_id,
        ):
            self.issued_events.append({
                "student_id": student_id,
                "course_id": course_id,
                "event_id": source_event_id,
            })

        self.ledger = InMemorySyncLedger()

        self.sync_service = ClassroomSyncService(
            classroom_service=ClassroomService(),
            issuer=fake_issuer,
            ledger=self.ledger,
        )

    def test_eligible_course_is_issued(self):
        result = self.sync_service.synchronize()

        self.assertEqual(result.eligible, 1)
        self.assertEqual(result.issued, 1)
        self.assertEqual(result.failed, 0)

        self.assertEqual(
            self.issued_events[0]["event_id"],
            "CLASSROOM-EVT-001",
        )

    def test_repeated_sync_skips_processed_event(self):
        first = self.sync_service.synchronize()
        second = self.sync_service.synchronize()

        self.assertEqual(first.issued, 1)
        self.assertEqual(second.issued, 0)
        self.assertEqual(second.skipped, 1)
        self.assertEqual(len(self.issued_events), 1)

    def test_failed_issuance_is_not_marked_processed(self):
        def failing_issuer(**kwargs):
            raise RuntimeError("Simulated issuance failure")

        service = ClassroomSyncService(
            classroom_service=ClassroomService(),
            issuer=failing_issuer,
            ledger=self.ledger,
        )

        result = service.synchronize()

        self.assertEqual(result.failed, 1)
        self.assertEqual(result.issued, 0)
        self.assertFalse(
            self.ledger.is_processed("CLASSROOM-EVT-001")
        )
