from django.core.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, BasePermission, IsAuthenticated

from .authorization import (
    get_authenticated_student_id,
    has_admin_permission,
    user_can_access_student,
)


def authorized_student_id(user):
    """Backward-compatible alias for the Developer 2 identity helper."""

    return get_authenticated_student_id(user)


class IsAdmin(BasePermission):
    """Compatibility permission requiring an explicit default admin grant."""

    message = "Administrator access required."

    def has_permission(self, request, view):
        permission = getattr(view, "required_permission", "accounts.access_admin_api")
        return has_admin_permission(request.user, permission)


class IsAdminWithPermission(IsAdmin):
    """Require the exact Django permission named by the view."""

    def has_permission(self, request, view):
        permission = getattr(view, "required_permission", None)
        return bool(permission and has_admin_permission(request.user, permission))


class IsVerifiedAuthenticated(IsAuthenticated):
    """Private API access requires an active account with verified email."""

    message = "An active, email-verified account is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            super().has_permission(request, view)
            and getattr(user, "is_active", False)
            and getattr(user, "is_email_verified", False)
        )


class IsStudent(BasePermission):
    """Allow only active student accounts linked to their canonical Student row."""

    message = "An active linked student account is required."

    def has_permission(self, request, view):
        try:
            authorized_student_id(request.user)
            return True
        except PermissionDenied:
            return False


class OwnStudentProfile(IsStudent):
    """Developer 2 compatibility class for Student objects only."""

    def has_object_permission(self, request, view, obj):
        from apps.students.models import Student

        try:
            return isinstance(obj, Student) and obj.pk == authorized_student_id(request.user)
        except PermissionDenied:
            return False


class IsOwnStudent(IsStudent):
    """Object permission for Student model instances or UUIDs."""

    message = "Student record access denied."

    def has_object_permission(self, request, view, obj):
        return user_can_access_student(request.user, getattr(obj, "pk", obj))


class IsOwnPassport(IsStudent):
    message = "Passport access denied."

    def has_object_permission(self, request, view, obj):
        passport = getattr(obj, "passport", obj)
        return user_can_access_student(request.user, getattr(passport, "student_id", None))


class IsOwnCredential(IsStudent):
    message = "Credential access denied."

    def has_object_permission(self, request, view, obj):
        return user_can_access_student(request.user, getattr(obj, "student_id", None))


class IsOwnPassportDocument(IsStudent):
    message = "Passport document access denied."

    def has_object_permission(self, request, view, obj):
        version = getattr(obj, "passport_version", None)
        passport = getattr(version, "passport", None)
        return user_can_access_student(request.user, getattr(passport, "student_id", None))


class IsPublicVerification(BasePermission):
    """Public verification may expose authenticity data, not private profile data."""

    def has_permission(self, request, view):
        return request.method in ("GET", "POST", "HEAD", "OPTIONS")
