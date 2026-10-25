
from datetime import date

from apps.skills.achievement_services import (
    record_verified_achievements,
)


def award_classroom_skills(record, skill_codes):
    """
    Award verified AI skills from an already
    validated, trusted Classroom completion.
    """

    if not skill_codes:
        raise ValueError("No skill mapping exists")

    earned_on = date.fromisoformat(
        record["completion_date"]
    )

    awards, created = record_verified_achievements(
        source="BTU_CLASSROOM",
        source_event_id=record["event_id"],
        external_student_id=record["student_id"],
        approved_skill_codes=skill_codes,
        earned_on=earned_on,
        verification_status="VERIFIED",
        course_id=record["course_id"],
        evidence_reference=(
            f"BTU_CLASSROOM:{record['event_id']}"
        ),
        evidence={
            "grade": record["grade"],
            "passed": record["passed"],
            "completion_status": record["completion_status"],
        },
    )

    return {
        "created": created,
        "achievement_ids": [
            str(award.id) for award in awards
        ],
        "skills_awarded": len(awards) if created else 0,
    }
