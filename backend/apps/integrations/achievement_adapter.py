
from datetime import date

from apps.skills.achievement_services import (
    record_verified_achievements,
)


def award_classroom_skills(record, skill_codes, *, source="BTU_CLASSROOM"):
    """
    Award verified AI skills from an already
    validated, trusted Classroom completion.
    """

    if not skill_codes:
        raise ValueError("No skill mapping exists")

    earned_on = date.fromisoformat(
        record["completion_date"]
    )

    grade = record['grade']
    if source in ('BTU_EXCEL', 'BTU_GOOGLE_SHEETS'):
        # Old Excel receipts encoded integer grades; preserve that representation
        # on semantically equal replays without rewriting the shared receipt.
        from apps.skills.models import AchievementSourceEvent
        evidence = AchievementSourceEvent.objects.filter(
            source=source, source_event_id=record['event_id'],
        ).values_list('evidence', flat=True).first()
        old_grade = evidence.get('grade') if isinstance(evidence, dict) else None
        if isinstance(old_grade, (int, float)) and not isinstance(old_grade, bool) and old_grade == grade:
            grade = old_grade

    awards, created = record_verified_achievements(
        source=source,
        source_event_id=record["event_id"],
        external_student_id=record["student_id"],
        approved_skill_codes=skill_codes,
        earned_on=earned_on,
        verification_status="VERIFIED",
        course_id=record["course_id"],
        evidence_reference=(
            f"{source}:{record['event_id']}"
        ),
        evidence={
            "grade": grade,
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
