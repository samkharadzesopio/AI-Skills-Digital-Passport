from rest_framework.exceptions import PermissionDenied
from django.db import transaction
from apps.students.models import Student
from .models import GoogleIdentity, PortalStudentMapping, SecurityAudit, User
from .otp_utils import normalize_btu_email, security_digest


def workspace_user(user):
    """Sessions are allowed for Workspace principals, including alumni/no records."""
    if (not user or not user.is_authenticated or not user.is_active or not user.is_email_verified
            or user.role != User.Role.STUDENT or user.is_staff or user.is_superuser
            or not GoogleIdentity.objects.filter(user=user).exists()):
        raise PermissionDenied('Verified BTU Workspace portal access required.')
    try:
        normalize_btu_email(user.email)
    except ValueError:
        raise PermissionDenied('Verified BTU Workspace portal access required.') from None
    return user


def owned_student_id(user):
    # The existing protected association was established by an earlier trusted
    # workflow. A new portal principal never obtains one from matching email.
    if not user.portal_only:
        return user.student_id
    mapping = PortalStudentMapping.objects.filter(google_identity__user=user).first()
    return Student.objects.filter(external_student_id=mapping.external_student_id).values_list('pk', flat=True).first() if mapping else None


@transaction.atomic
def approve_mapping(*, actor, subject, external_student_id, approval_reference):
    from .authorization import require_admin_permission
    require_admin_permission(actor, 'accounts.manage_student_accounts')
    if (not isinstance(external_student_id, str) or not external_student_id.strip() or len(external_student_id) > 120
            or external_student_id != external_student_id.strip() or not isinstance(approval_reference, str)
            or not approval_reference.strip() or len(approval_reference) > 255):
        raise ValueError('Explicit institutional identifier and approval reference required.')
    identity = GoogleIdentity.objects.select_for_update().get(subject=subject)
    if GoogleIdentity.objects.filter(user__student__external_student_id=external_student_id).exclude(pk=identity.pk).exists():
        raise ValueError('Institutional identifier already has a trusted Google binding.')
    if identity.user.student_id:
        if not Student.objects.filter(pk=identity.user.student_id, external_student_id=external_student_id).exists():
            raise ValueError('Existing trusted association conflicts; no automatic reassignment.')
    existing = PortalStudentMapping.objects.filter(google_identity=identity).first()
    if existing:
        if existing.external_student_id != external_student_id:
            raise ValueError('Mapping cannot be reassigned.')
        return existing
    result = PortalStudentMapping.objects.create(google_identity=identity, external_student_id=external_student_id,
        approval_reference=approval_reference.strip(), approved_by=actor)
    SecurityAudit.objects.create(actor=actor, action='PortalStudentMapping:APPROVED',
        ip_digest=security_digest('security.audit.ip', 'trusted-operator'), status_code=200)
    return result
