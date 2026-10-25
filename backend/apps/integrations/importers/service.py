
from datetime import date

from apps.integrations.repositories import (
    ApprovedAICourseRepository,
)
from apps.skills.achievement_services import (
    record_verified_achievements,
)

from .validators import (
    validate_completion_record,
    ImportValidationError,
)


ALLOWED_SOURCES = {
    "BTU_GOOGLE_SHEETS",
    "BTU_EXCEL",
}


def process_completion_import(
    records,
    *,
    source,
    award_func=None,
    course_repository=None,
):
    """
    Process completion records from an already
    authenticated, trusted university source.

    An import is not proof of authenticity by itself.
    """

    if source not in ALLOWED_SOURCES:
        raise ImportValidationError(
            "Unsupported import source"
        )

    award_func = (
        award_func
        if award_func is not None
        else record_verified_achievements
    )

    repository = (
        course_repository
        if course_repository is not None
        else ApprovedAICourseRepository()
    )

    courses = {
        course["course_id"]: course
        for course in repository.get_approved_courses()
    }

    result = {
        "processed": 0,
        "awarded": 0,
        "skipped": 0,
        "failed": 0,
        "errors": [],
    }

    for row_number, raw_record in enumerate(
        records, start=2
    ):
        result["processed"] += 1

        try:
            record = validate_completion_record(
                raw_record
            )

            course = courses.get(
                record["course_id"]
            )

            if course is None:
                raise ImportValidationError(
                    "Course is not in the trusted AI catalog"
                )

            if record["grade"] < course["minimum_grade"]:
                raise ImportValidationError(
                    "Grade is below the course passing threshold"
                )

            skill_codes = course.get("skill_codes")

            if not skill_codes:
                raise ImportValidationError(
                    "Course has no skill mapping"
                )

            awards, created = award_func(
                source=source,
                source_event_id=record["source_event_id"],
                external_student_id=record[
                    "external_student_id"
                ],
                approved_skill_codes=skill_codes,
                earned_on=date.fromisoformat(
                    record["completion_date"]
                ),
                verification_status="VERIFIED",
                course_id=record["course_id"],
                evidence_reference=(
                    f"{source}:"
                    f"{record['source_event_id']}"
                ),
                evidence={
                    "grade": record["grade"],
                    "passed": record["passed"],
                    "completion_status": record[
                        "completion_status"
                    ],
                },
            )

            if created:
                result["awarded"] += len(awards)
            else:
                result["skipped"] += 1

        except Exception as exc:
            result["failed"] += 1
            result["errors"].append({
                "row": row_number,
                "type": type(exc).__name__,
                "message": str(exc),
            })

    return result
