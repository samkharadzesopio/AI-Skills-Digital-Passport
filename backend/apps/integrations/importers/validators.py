
import math
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
    """Validate and normalize a completion record."""

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

    identifiers = {}

    for field in (
        "external_student_id",
        "course_id",
        "source_event_id",
    ):
        value = record[field]

        if (
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or len(value) > 120
            or any(ord(char) < 32 for char in value)
        ):
            raise ImportValidationError(
                f"Invalid {field}"
            )

        identifiers[field] = value

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
        or not math.isfinite(grade)
        or not 0 <= grade <= 100
    ):
        raise ImportValidationError(
            "Grade must be a finite number between 0 and 100"
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

    if (
        not isinstance(completion_date, date)
        or completion_date > date.today()
    ):
        raise ImportValidationError(
            "Invalid or future completion date"
        )

    return {
        **identifiers,
        "completion_status": "completed",
        "passed": True,
        "grade": grade,
        "completion_date": completion_date.isoformat(),
    }
