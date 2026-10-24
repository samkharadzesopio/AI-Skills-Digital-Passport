
from .clients import MockBTUClassroomClient
from .repositories import ApprovedAICourseRepository


class ClassroomService:
    def __init__(self, client=None, course_repository=None):
        self.client = (
            client if client is not None
            else MockBTUClassroomClient()
        )
        self.course_repository = (
            course_repository if course_repository is not None
            else ApprovedAICourseRepository()
        )

    def get_completions(self):
        return self.client.fetch_completions()

    def get_eligible_completions(self):
        records = self.get_completions()
        approved_courses = {
            course["course_id"]: course
            for course in self.course_repository.get_approved_courses()
        }

        eligible = []
        seen_events = set()

        for record in records:
            event_id = record.get("event_id")
            course_id = record.get("course_id")
            approved_course = approved_courses.get(course_id)

            if not event_id or event_id in seen_events:
                continue

            if not approved_course:
                continue

            if record.get("completion_status") != "completed":
                continue

            if record.get("passed") is not True:
                continue

            grade = record.get("grade")

            if (
                not isinstance(grade, (int, float))
                or isinstance(grade, bool)
                or grade < approved_course["minimum_grade"]
                or grade > 100
            ):
                continue

            if not record.get("student_id"):
                continue

            if not record.get("completion_date"):
                continue

            eligible.append(record)
            seen_events.add(event_id)

        return eligible

