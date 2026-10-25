from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

def authorized_student_id(user):
    if not user or not getattr(user, 'is_authenticated', False) or not getattr(user, 'pk', None):
        raise PermissionDenied('Student access required.')
    from .identity import authorized_student_id as resolve
    return resolve(user)


class IsAdmin(BasePermission):
    """Staff privilege is explicit; student accounts cannot act as administrators."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active
                    and user.is_staff and not getattr(user, 'student_id', None))


class IsStudent(BasePermission):
    def has_permission(self, request, view):
        try:
            authorized_student_id(request.user)
            return True
        except PermissionDenied:
            return False


class OwnStudentProfile(IsStudent):
    """Only for Student objects. Lists must ALSO filter using the helper."""

    def has_object_permission(self, request, view, obj):
        from apps.students.models import Student
        try:
            return isinstance(obj, Student) and obj.pk == authorized_student_id(request.user)
        except PermissionDenied:
            return False


class IsPublicVerification(BasePermission):
    def has_permission(self, request, view):
        return request.method in ('GET', 'POST', 'HEAD', 'OPTIONS')
