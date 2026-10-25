
from types import SimpleNamespace

from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from .permissions import (
    IsAdmin,
    IsStudent,
    IsPublicVerification,
)


class AccountPermissionTests(SimpleTestCase):

    def setUp(self):
        self.factory = APIRequestFactory()

    def request_as(self, *, authenticated, staff=False,
                   active=True):
        request = self.factory.get("/")

        request.user = SimpleNamespace(
            is_authenticated=authenticated,
            is_staff=staff,
            is_active=active,
        )

        return request

    def test_admin_allowed(self):
        request = self.request_as(
            authenticated=True,
            staff=True,
        )

        self.assertTrue(
            IsAdmin().has_permission(request, None)
        )

    def test_student_cannot_access_admin(self):
        request = self.request_as(
            authenticated=True,
        )

        self.assertFalse(
            IsAdmin().has_permission(request, None)
        )

    def test_anonymous_cannot_access_admin(self):
        request = self.request_as(
            authenticated=False,
        )

        self.assertFalse(
            IsAdmin().has_permission(request, None)
        )

    def test_unlinked_user_denied(self):
        request = self.request_as(
            authenticated=True,
        )

        self.assertFalse(
            IsStudent().has_permission(request, None)
        )

    def test_admin_not_treated_as_student(self):
        request = self.request_as(
            authenticated=True,
            staff=True,
        )

        self.assertFalse(
            IsStudent().has_permission(request, None)
        )

    def test_inactive_user_denied(self):
        request = self.request_as(
            authenticated=True,
            active=False,
        )

        self.assertFalse(
            IsStudent().has_permission(request, None)
        )

    def test_public_verification_allowed(self):
        request = self.request_as(
            authenticated=False,
        )

        self.assertTrue(
            IsPublicVerification().has_permission(
                request, None
            )
        )
