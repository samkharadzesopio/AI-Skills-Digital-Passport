from uuid import UUID

from .models import Skill


class SkillRepository:
    """Read-only catalog lookups using the configured Django database."""

    def get_by_code(self, skill_code: str) -> Skill | None:
        """Match the skill code exactly, without normalization."""
        if not isinstance(skill_code, str) or not skill_code:
            return None
        try:
            return Skill.objects.get(skill_code=skill_code)
        except Skill.DoesNotExist:
            return None

    def get_by_id(self, skill_uuid: UUID | str) -> Skill | None:
        """Accept a UUID object or UUID string; malformed identifiers return None."""
        if isinstance(skill_uuid, str):
            try:
                skill_uuid = UUID(skill_uuid)
            except ValueError:
                return None
        if not isinstance(skill_uuid, UUID):
            return None
        try:
            return Skill.objects.get(pk=skill_uuid)
        except Skill.DoesNotExist:
            return None

    def exists_by_code(self, skill_code: str) -> bool:
        if not isinstance(skill_code, str) or not skill_code:
            return False
        return Skill.objects.filter(skill_code=skill_code).exists()
