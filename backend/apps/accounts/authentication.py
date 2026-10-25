from django.contrib.auth.backends import ModelBackend
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied

from .identity import authorized_student_id


class StudentOTPBackend(ModelBackend):
    """Session loader only: never accept passwords or caller-supplied user IDs."""

    def authenticate(self, request, **credentials):
        return None

    def get_user(self, user_id):
        user = super().get_user(user_id)
        try:
            authorized_student_id(user)
            return user
        except PermissionDenied:
            return None


class AdminPasswordBackend(ModelBackend):
    def user_can_authenticate(self, user):
        return bool(super().user_can_authenticate(user) and user.is_staff
                    and not user.student_id)


class AccountSessionAuthentication(SessionAuthentication):
    """Also revalidate linkage for sessions loaded through other configured backends."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result:
            user, _ = result
            if not user.is_staff:
                authorized_student_id(user)
            elif user.student_id:
                raise PermissionDenied('Invalid administrator identity.')
        return result
