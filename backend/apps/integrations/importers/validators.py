
from datetime import date, datetime


class ImportValidationError(ValueError):
    pass


REQUIRED_FIELDS = (
    "external_student_id",
    "course_id",
    "completion_status",
    "grade",
    "passed",
    "completion_date",
    "source_event_id",
)


def validate_completion_record(record):
    """Validate a spreadsheet completion record."""

    if not isinstance(record, dict):
        raise ImportValidationError(
            "Record must be a dictionary"
        )

    missing = [
        field for field in REQUIRED_FIELDS
        if field not in record
    ]

    if missing:
        raise ImportValidationError(
            f"Missing fields: {', '.join(missing)}"
        )

    student_id = str(
        record["external_student_id"]
    ).strip()

    course_id = str(record["course_id"]).strip()
    event_id = str(
        record["source_event_id"]
    ).strip()

    if not student_id or not course_id or not event_id:
        raise ImportValidationError(
            "Student, course and event IDs are required"
        )

    if record["completion_status"] != "completed":
        raise ImportValidationError(
            "Course is not completed"
        )

    if record["passed"] is not True:
        raise ImportValidationError(
            "Course was not passed"
        )

    grade = record["grade"]

    if (
        isinstance(grade, bool)
        or not isinstance(grade, (int, float))
        or not 0 <= grade <= 100
    ):
        raise ImportValidationError(
            "Grade must be between 0 and 100"
        )

    completion_date = record["completion_date"]

    if isinstance(completion_date, datetime):
        completion_date = completion_date.date()
    elif isinstance(completion_date, str):
        try:
            completion_date = date.fromisoformat(
                completion_date
            )
        except ValueError as exc:
            raise ImportValidationError(
                "Invalid completion date"
            ) from exc

    if not isinstance(completion_date, date):
        raise ImportValidationError(
            "Completion date is required"
        )

    return {
        "external_student_id": student_id,
        "course_id": course_id,
        "source_event_id": event_id,
        "completion_status": "completed",
        "passed": True,
        "grade": grade,
        "completion_date": completion_date.isoformat(),
    }
