
from dataclasses import dataclass
from typing import Callable, Protocol

from .services import ClassroomService


class SyncLedger(Protocol):
    def is_processed(self, event_id: str) -> bool:
        ...

    def mark_processed(self, event_id: str) -> None:
        ...


@dataclass
class SyncResult:
    eligible: int = 0
    issued: int = 0
    skipped: int = 0
    failed: int = 0


class ClassroomSyncService:
    def __init__(
        self,
        classroom_service: ClassroomService,
        issuer: Callable,
        ledger: SyncLedger,
    ):
        self.classroom_service = classroom_service
        self.issuer = issuer
        self.ledger = ledger

    def synchronize(self) -> SyncResult:
        records = (
            self.classroom_service
            .get_eligible_completions()
        )

        result = SyncResult(eligible=len(records))

        for record in records:
            event_id = record["event_id"]

            if self.ledger.is_processed(event_id):
                result.skipped += 1
                continue

            try:
                self.issuer(
                    student_id=record["student_id"],
                    course_id=record["course_id"],
                    source_event_id=event_id,
                )

                self.ledger.mark_processed(event_id)
                result.issued += 1

            except Exception:
                result.failed += 1

        return result


from .achievement_adapter import award_classroom_skills
from .repositories import ApprovedAICourseRepository


class DatabaseClassroomSyncService:
    """
    Synchronizes eligible Classroom completions
    using Developer 1's persistent achievement service.
    """

    def __init__(self, classroom_service=None,
                 course_repository=None, award_func=None):
        self.classroom_service = (
            classroom_service or ClassroomService()
        )
        self.course_repository = (
            course_repository or ApprovedAICourseRepository()
        )
        self.award_func = award_func or award_classroom_skills

    def synchronize(self):
        courses = {
            course["course_id"]: course
            for course in
            self.course_repository.get_approved_courses()
        }

        eligible_records = (
            self.classroom_service.get_eligible_completions()
        )

        result = {
            "eligible": len(eligible_records),
            "issued": 0,
            "skipped": 0,
            "failed": 0,
            "errors": [],
        }

        for record in eligible_records:
            event_id = record["event_id"]

            try:
                course = courses[record["course_id"]]
                skill_codes = course.get("skill_codes")

                if not skill_codes:
                    raise ValueError(
                        "Course has no skill mapping"
                    )

                outcome = self.award_func(
                    record=record,
                    skill_codes=skill_codes,
                )

                if outcome["created"]:
                    result["issued"] += 1
                else:
                    result["skipped"] += 1

            except Exception as exc:
                result["failed"] += 1
                result["errors"].append({
                    "event_id": event_id,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                })

        return result
