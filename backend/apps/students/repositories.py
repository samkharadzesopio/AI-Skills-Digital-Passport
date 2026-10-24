from uuid import UUID

from .models import Student


class StudentRepository:
    """Read-only student lookups using the configured Django database."""

    def get_by_external_id(self, student_id: str) -> Student | None:
        """Match the external identifier exactly, without normalization."""
        if not isinstance(student_id, str) or not student_id:
            return None
        try:
            return Student.objects.get(external_student_id=student_id)
        except Student.DoesNotExist:
            return None

    def get_by_id(self, student_uuid: UUID | str) -> Student | None:
        """Accept a UUID object or UUID string; malformed identifiers return None."""
        if isinstance(student_uuid, str):
            try:
                student_uuid = UUID(student_uuid)
            except ValueError:
                return None
        if not isinstance(student_uuid, UUID):
            return None
        try:
            return Student.objects.get(pk=student_uuid)
        except Student.DoesNotExist:
            return None

    def exists_by_external_id(self, student_id: str) -> bool:
        if not isinstance(student_id, str) or not student_id:
            return False
        return Student.objects.filter(external_student_id=student_id).exists()
