from django.contrib.auth.backends import ModelBackend
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied

from .identity import authorized_student_id
from .models import User


class StudentOTPBackend(ModelBackend):
    """Session loader only: never accept passwords or caller-supplied user IDs."""

    def authenticate(self, request, **credentials):
        return None

    def get_user(self, user_id):
        user = User.objects.select_related('student').filter(pk=user_id).first()
        if user is None:
            return None
        # The linked Student and status were loaded in this same DB query, so
        # the central helper can validate without issuing another query.
        user._accounts_identity_authoritative = True
        try:
            authorized_student_id(user)
            return user
        except PermissionDenied:
            return None


class AdminPasswordBackend(ModelBackend):
    def user_can_authenticate(self, user):
        return bool(
            super().user_can_authenticate(user)
            and user.role == User.Role.ADMIN
            and user.is_staff
            and not user.is_superuser
            and not user.student_id
        )


class AccountSessionAuthentication(SessionAuthentication):
    """Also revalidate linkage for sessions loaded through other configured backends."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result:
            user, _ = result
            if not user.is_staff:
                authorized_student_id(user)
            elif (
                user.role != User.Role.ADMIN
                or user.student_id
                or user.is_superuser
            ):
                raise PermissionDenied('Invalid administrator identity.')
        return result
