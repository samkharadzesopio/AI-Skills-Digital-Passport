
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
