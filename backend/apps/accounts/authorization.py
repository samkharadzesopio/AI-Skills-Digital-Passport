from uuid import UUID

from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied

from .models import User


# Public capabilities name product actions, never internal permission records.
ADMIN_CAPABILITIES = (
    'view_student_records', 'manage_student_accounts', 'manage_credentials',
    'revoke_credentials', 'sync_classroom', 'import_completions',
)


def admin_capabilities(user):
    return [name for name in ADMIN_CAPABILITIES
            if has_admin_permission(user, f'accounts.{name}')]


def has_admin_permission(user, permission):
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and getattr(user, "is_email_verified", False)
        and getattr(user, "role", None) == User.Role.ADMIN
        and getattr(user, "is_staff", False)
        and not getattr(user, "is_superuser", False)
        and isinstance(permission, str)
        and user.has_perm(permission)
    )


def require_admin_permission(user, permission):
    if not has_admin_permission(user, permission):
        raise PermissionDenied("Administrator permission required.")
    return True


def get_authenticated_student_id(user) -> UUID:
    """Return only the Student UUID linked in the authenticated User row."""

    if (
        not user
        or not getattr(user, "is_authenticated", False)
        or not getattr(user, "is_active", False)
        or not getattr(user, "is_email_verified", False)
        or getattr(user, "role", None) != User.Role.STUDENT
    ):
        raise PermissionDenied("An active student account is required.")
    student_id = getattr(user, "student_id", None)
    if student_id is None:
        raise PermissionDenied("No student record is linked to this account.")
    if isinstance(user, User):
        # The persisted Student status and email-to-account association are
        # authoritative. This single joined lookup also rejects stale sessions.
        from .identity import authorized_student_id as resolve_student_id

        try:
            resolved = resolve_student_id(user)
            # Cache the fresh database validation for the lifetime of this
            # request's User object; subsequent object checks avoid repeat SQL.
            user._accounts_identity_authoritative = True
            return resolved
        except DRFPermissionDenied:
            raise PermissionDenied("Student access required.") from None
    try:
        return UUID(str(student_id))
    except (TypeError, ValueError, AttributeError):
        raise PermissionDenied("The student account link is invalid.") from None


def user_can_access_student(user, student_id):
    try:
        requested = UUID(str(student_id))
        linked = get_authenticated_student_id(user)
    except (TypeError, ValueError, AttributeError, PermissionDenied):
        return False
    return linked == requested


def require_own_student(user, student_id):
    if not user_can_access_student(user, student_id):
        raise PermissionDenied("Student record access denied.")
    return True


def authorize_credential_revocation(actor, credential):
    require_admin_permission(actor, "accounts.revoke_credentials")
    return f"account:{actor.pk}"
