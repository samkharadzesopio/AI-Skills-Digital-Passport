
from django.test import SimpleTestCase
from unittest.mock import Mock

from .sync import DatabaseClassroomSyncService


class DatabaseClassroomSyncTests(SimpleTestCase):

    def test_completed_ai_course_awards_skills(self):
        fake_award = Mock(
            return_value={"created": True}
        )

        service = DatabaseClassroomSyncService(
            award_func=fake_award
        )

        result = service.synchronize()

        self.assertEqual(result["eligible"], 1)
        self.assertEqual(result["issued"], 1)
        self.assertEqual(result["failed"], 0)

        fake_award.assert_called_once()

        args = fake_award.call_args.kwargs

        self.assertEqual(
            args["record"]["course_id"], "AI-101"
        )
        self.assertEqual(
            args["skill_codes"],
            ["AI_LITERACY", "AI_FUNDAMENTALS"]
        )

    def test_repeated_event_is_skipped(self):
        fake_award = Mock(
            return_value={"created": False}
        )

        result = DatabaseClassroomSyncService(
            award_func=fake_award
        ).synchronize()

        self.assertEqual(result["issued"], 0)
        self.assertEqual(result["skipped"], 1)

    def test_failed_award_is_reported(self):
        fake_award = Mock(
            side_effect=ValueError("Unknown skill")
        )

        result = DatabaseClassroomSyncService(
            award_func=fake_award
        ).synchronize()

        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["issued"], 0)
        self.assertEqual(
            result["errors"][0]["error_type"],
            "ValueError"
        )
