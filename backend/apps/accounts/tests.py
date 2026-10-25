from datetime import timedelta
from io import StringIO
from types import SimpleNamespace
from uuid import uuid4

from django.core.management import call_command
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory

from .authorization import (
    authorize_credential_revocation,
    get_authenticated_student_id,
    user_can_access_student,
)
from .permissions import (
    IsAdmin,
    IsAdminWithPermission,
    IsOwnStudent,
    IsPublicVerification,
    IsStudent,
    OwnStudentProfile,
)
from .models import AuthRateLimitBucket, LoginChallenge, LoginRateBucket, OTPChallenge


class AccountPermissionTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.student_id = uuid4()

    def user(
        self,
        *,
        authenticated=True,
        role="STUDENT",
        active=True,
        email_verified=True,
        staff=False,
        superuser=False,
        student_id=None,
        permissions=(),
    ):
        return SimpleNamespace(
            pk=uuid4(),
            is_authenticated=authenticated,
            role=role,
            is_active=active,
            is_email_verified=email_verified,
            is_staff=staff,
            is_superuser=superuser,
            student_id=student_id,
            has_perm=lambda permission: permission in permissions,
        )

    def test_student_cannot_access_admin(self):
        request = self.factory.get("/")
        request.user = self.user(student_id=self.student_id)
        self.assertFalse(IsAdmin().has_permission(request, None))

    def test_anonymous_cannot_access_admin_or_student_data(self):
        request = self.factory.get("/")
        request.user = self.user(authenticated=False)
        self.assertFalse(IsAdmin().has_permission(request, None))
        self.assertFalse(IsStudent().has_permission(request, None))

    def test_admin_requires_role_staff_and_explicit_permission(self):
        request = self.factory.get("/")
        request.user = self.user(
            role="ADMIN", staff=True, permissions={"accounts.access_admin_api"}
        )
        self.assertTrue(IsAdmin().has_permission(request, None))
        request.user = self.user(role="ADMIN", staff=True)
        self.assertFalse(IsAdmin().has_permission(request, None))
        request.user = self.user(
            role="STUDENT", staff=True, permissions={"accounts.access_admin_api"}
        )
        self.assertFalse(IsAdmin().has_permission(request, None))

    def test_action_permission_is_exact(self):
        request = self.factory.post("/")
        request.user = self.user(
            role="ADMIN", staff=True, permissions={"accounts.import_completions"}
        )
        view = SimpleNamespace(required_permission="accounts.import_completions")
        self.assertTrue(IsAdminWithPermission().has_permission(request, view))
        view.required_permission = "accounts.revoke_credentials"
        self.assertFalse(IsAdminWithPermission().has_permission(request, view))

    def test_student_id_is_only_read_from_valid_account_link(self):
        user = self.user(student_id=self.student_id)
        self.assertEqual(get_authenticated_student_id(user), self.student_id)
        self.assertTrue(user_can_access_student(user, self.student_id))
        self.assertFalse(user_can_access_student(user, uuid4()))
        for invalid in (
            self.user(authenticated=False, student_id=self.student_id),
            self.user(active=False, student_id=self.student_id),
            self.user(email_verified=False, student_id=self.student_id),
            self.user(role="ADMIN", staff=True, student_id=self.student_id),
            self.user(student_id=None),
        ):
            with self.assertRaises(PermissionDenied):
                get_authenticated_student_id(invalid)

    def test_public_verification_is_available_without_login(self):
        request = self.factory.get("/")
        request.user = self.user(authenticated=False)
        self.assertTrue(IsPublicVerification().has_permission(request, None))

    def test_credential_revocation_policy_fails_closed(self):
        actor = self.user(
            role="ADMIN", staff=True, permissions={"accounts.revoke_credentials"}
        )
        self.assertEqual(
            authorize_credential_revocation(actor, object()), f"account:{actor.pk}"
        )
        with self.assertRaises(PermissionDenied):
            authorize_credential_revocation(
                self.user(role="STUDENT", student_id=self.student_id), object()
            )
        with self.assertRaises(PermissionDenied):
            authorize_credential_revocation(self.user(role="ADMIN", staff=True), object())


class AuthStateCleanupTests(TestCase):
    def test_cleanup_removes_expired_login_and_recovery_state(self):
        expired = timezone.now() - timedelta(days=2)
        OTPChallenge.objects.create(
            purpose=OTPChallenge.Purpose.PASSWORD_RESET,
            email_digest="a" * 64,
            ip_digest="b" * 64,
            code_digest="c" * 64,
            expires_at=expired,
        )
        AuthRateLimitBucket.objects.create(
            bucket_digest="d" * 64,
            window_started_at=expired,
        )
        LoginChallenge.objects.create(
            subject="e" * 64,
            code_hash="f" * 64,
            expires_at=expired,
        )
        LoginRateBucket.objects.create(key="0" * 64, window_started_at=expired)

        call_command("purge_expired_auth_state", stdout=StringIO())

        self.assertFalse(OTPChallenge.objects.exists())
        self.assertFalse(AuthRateLimitBucket.objects.exists())
        self.assertFalse(LoginChallenge.objects.exists())
        self.assertFalse(LoginRateBucket.objects.exists())
