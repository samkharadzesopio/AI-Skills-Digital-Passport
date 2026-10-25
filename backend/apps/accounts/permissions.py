
from rest_framework.permissions import (
    BasePermission,
    IsAuthenticated,
)


class IsAdmin(BasePermission):
    """Allow authenticated university administrators only."""

    message = "Administrator access required."

    def has_permission(self, request, view):
        user = request.user

        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.is_staff
        )


class IsStudent(IsAuthenticated):
    """
    Temporary student-role foundation.

    Student-specific ownership must be checked
    separately once accounts are linked to
    Student records.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False

        user = request.user

        return bool(
            user.is_active
            and not user.is_staff
        )


class IsPublicVerification(BasePermission):
    """
    Public verification endpoints.

    Views using this permission must expose only
    limited authenticity results, never private
    student records.
    """

    def has_permission(self, request, view):
        return request.method in ("GET", "POST", "HEAD", "OPTIONS")
