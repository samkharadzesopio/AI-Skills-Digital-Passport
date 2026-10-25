from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from apps.students.models import Student
from .models import User
from .otp_utils import normalize_btu_email


def active_student_statuses():
    values = getattr(settings, 'ACCOUNTS_ACTIVE_STUDENT_STATUSES', None)
    if not isinstance(values, (list, tuple)) or not values or not all(
        isinstance(v, str) and v for v in values
    ):
        raise ImproperlyConfigured('Explicit ACCOUNTS_ACTIVE_STUDENT_STATUSES required.')
    return values


def authorized_student_id(user):
    """Return canonical Student UUID or raise PermissionDenied. DB is authoritative."""
    if not user or not user.is_authenticated or not getattr(user, 'pk', None):
        raise PermissionDenied('Student access required.')
    if (
        not getattr(user, 'is_active', False)
        or getattr(user, 'is_staff', False)
        or getattr(user, 'is_superuser', False)
        or not getattr(user, 'is_email_verified', False)
        or not getattr(user, 'student_id', None)
    ):
        raise PermissionDenied('Student access required.')
    if getattr(user, '_accounts_identity_authoritative', False):
        account = user
    else:
        account = User.objects.filter(
            pk=user.pk, is_active=True, is_staff=False, is_superuser=False,
            is_email_verified=True,
            student__student_status__in=active_student_statuses(),
        ).select_related('student').first()
    if account and account.student_id:
        try:
            student = account.student
            if (
                student.student_status in active_student_statuses()
                and normalize_btu_email(student.email) == normalize_btu_email(account.email)
            ):
                return account.student_id
        except ValueError:
            pass
    raise PermissionDenied('Student access required.')


@transaction.atomic
def provision_student_account(email):
    """Internal trusted-record lookup, NOT a public Student-ID linking interface.

    OTP verification proves mailbox control before this is called by the login flow.
    Inactive existing accounts are never reactivated here.
    """
    email = normalize_btu_email(email)
    student = Student.objects.select_for_update().filter(
        email__iexact=email, student_status__in=active_student_statuses(),
    ).first()
    if not student:
        raise PermissionDenied('Student access required.')
    existing = User.objects.select_for_update().filter(email__iexact=email).first()
    if existing:
        if (
            not existing.is_active
            or existing.is_staff
            or existing.is_superuser
            or existing.student_id != student.pk
        ):
            raise PermissionDenied('Student access required.')
        if not existing.is_email_verified:
            existing.is_email_verified = True
            existing.save(update_fields=['is_email_verified'])
        authorized_student_id(existing)
        return existing
    if User.objects.filter(student=student).exists():
        raise PermissionDenied('Student access required.')
    user = User(
        email=email,
        role=User.Role.STUDENT,
        is_email_verified=True,
        student=student,
    )
    user.set_unusable_password()
    user.save()
    return user
