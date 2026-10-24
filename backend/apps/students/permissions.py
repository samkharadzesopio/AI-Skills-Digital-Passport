from rest_framework.permissions import BasePermission


class StudentProfileAccessPending(BasePermission):
    """Deny access until the accounts team supplies an agreed access policy.

    Integration must authorize the requesting account for the requested student,
    including object-level access; authentication alone is insufficient.
    """

    message = "Student profile access is not enabled."

    def has_permission(self, request, view):
        return False
