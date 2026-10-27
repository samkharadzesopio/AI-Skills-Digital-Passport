import re

from django.core import mail
from django.db import IntegrityError, transaction
from django.contrib.auth.hashers import make_password
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from apps.students.models import Student

from .models import User
from .services import (
    InvalidInvitation,
    create_student_account_invitation,
    redeem_student_account_invitation,
)


PASSWORD = "Correct-Horse-Battery-2026!"
RESET_PASSWORD = "New-Correct-Horse-2026!"


def make_student(code, email):
    return Student.objects.create(
        external_student_id=code,
        first_name="Synthetic",
        last_name="Student",
        email=email,
        program="Computer Science",
        education_level="Bachelor",
        student_status="Active",
    )


class AuthAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.student_a = make_student("AUTH-0001", "student.a@btu.edu.ge")
        cls.student_b = make_student("AUTH-0002", "student.b@btu.edu.ge")
        cls.student_user = User.objects.create_user(
            email=cls.student_a.email,
            password=PASSWORD,
            student=cls.student_a,
            is_email_verified=True,
        )
        cls.admin = User.objects.create_admin_user(
            email="admin@btu.edu.ge",
            password=PASSWORD,
            permission_codenames={
                "manage_student_accounts",
                "revoke_credentials",
                "sync_classroom",
                "import_completions",
            },
        )

    def otp_login(self, email, client=None):
        client = client or self.client
        request_response = client.post(
            reverse("accounts:otp-request"), {"email": email}, format="json"
        )
        self.assertEqual(request_response.status_code, 202)
        code = re.search(r"code is: ([0-9]{6})", mail.outbox[-1].body).group(1)
        return client.post(
            reverse("accounts:otp-verify"),
            {"email": email, "code": code},
            format="json",
        )

    def test_student_login_and_current_user(self):
        response = self.otp_login(self.student_a.email)
        self.assertEqual(response.status_code, 200)
        current = self.client.get(reverse("accounts:current-user"))
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.data["email"], self.student_a.email)
        self.assertEqual(current.data["role"], "STUDENT")
        self.assertEqual(current.data["student_association"], "linked")

    def test_admin_login(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"email": self.admin.email, "password": PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], "ADMIN")
        self.assertEqual(response.data["student_association"], "unlinked")

    def test_unverified_admin_session_is_restricted_until_email_verification(self):
        admin = User.objects.create_admin_user(
            email="pending.admin@btu.edu.ge",
            password=PASSWORD,
            permission_codenames={"sync_classroom"},
        )
        User.objects.filter(pk=admin.pk).update(is_email_verified=False)
        login_response = self.client.post(
            reverse("accounts:login"),
            {"email": admin.email, "password": PASSWORD},
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertFalse(login_response.data["email_verified"])
        self.assertEqual(
            self.client.get("/api/integrations/classroom/completions/").status_code,
            403,
        )
        requested = self.client.post(reverse("accounts:email-verification-request"), {}, format="json")
        self.assertEqual(requested.status_code, 202)
        code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
        confirmed = self.client.post(
            reverse("accounts:email-verification-confirm"),
            {"code": code},
            format="json",
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(
            self.client.get("/api/integrations/classroom/completions/").status_code,
            200,
        )

    def test_invalid_password_and_inactive_accounts_are_generic(self):
        disabled = User.objects.create_user(
            email="disabled@btu.edu.ge",
            password=PASSWORD,
            is_active=False,
            is_email_verified=True,
        )
        unverified = User.objects.create_user(
            email="unverified@btu.edu.ge",
            password=PASSWORD,
            is_email_verified=False,
        )
        results = []
        for email, password in (
            (self.student_a.email, PASSWORD),
            (disabled.email, PASSWORD),
            ("unknown@btu.edu.ge", PASSWORD),
        ):
            response = self.client.post(
                reverse("accounts:login"),
                {"email": email, "password": password},
                format="json",
            )
            results.append((response.status_code, response.data))
        self.assertEqual({status for status, _ in results}, {401})
        self.assertEqual(len({str(body) for _, body in results}), 1)

    def test_unverified_account_can_only_access_email_verification_until_verified(self):
        unverified = User.objects.create_user(
            email=self.student_b.email,
            password=PASSWORD,
            student=self.student_b,
            is_email_verified=False,
        )
        self.client.force_authenticate(user=unverified)
        profile = self.client.get(
            reverse("students:student-profile", kwargs={"student_id": self.student_b.external_student_id})
        )
        self.assertEqual(profile.status_code, 403)
        requested = self.client.post(reverse("accounts:email-verification-request"), {}, format="json")
        self.assertEqual(requested.status_code, 202)
        code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
        confirmed = self.client.post(
            reverse("accounts:email-verification-confirm"),
            {"code": code},
            format="json",
        )
        self.assertEqual(confirmed.status_code, 200)
        self.assertTrue(User.objects.get(pk=unverified.pk).is_email_verified)
        self.client.force_authenticate(user=User.objects.get(pk=unverified.pk))
        profile = self.client.get(
            reverse("students:student-profile", kwargs={"student_id": self.student_b.external_student_id})
        )
        self.assertEqual(profile.status_code, 200)

    def test_student_can_read_only_the_linked_profile(self):
        self.client.force_authenticate(user=self.student_user)
        own = self.client.get(
            reverse("students:student-profile", kwargs={"student_id": self.student_a.external_student_id})
        )
        other = self.client.get(
            reverse("students:student-profile", kwargs={"student_id": self.student_b.external_student_id})
        )
        supplied_uuid = self.client.get(
            reverse("students:student-profile", kwargs={"student_id": str(self.student_b.pk)})
        )
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.data["student_id"], self.student_a.external_student_id)
        self.assertEqual(other.status_code, 404)
        self.assertEqual(supplied_uuid.status_code, 404)

    def test_missing_student_association_is_not_authorized(self):
        unlinked = User.objects.create_user(
            email="unlinked@btu.edu.ge",
            password=PASSWORD,
            is_email_verified=True,
        )
        self.client.force_authenticate(user=unlinked)
        response = self.client.get(
            reverse("students:student-profile", kwargs={"student_id": self.student_a.external_student_id})
        )
        self.assertEqual(response.status_code, 403)

    def test_invited_registration_uses_preprovisioned_student_not_client_uuid(self):
        self.client.force_authenticate(user=self.admin)
        invitation_response = self.client.post(
            reverse("accounts:student-invitation-create"),
            {"student_id": str(self.student_b.pk)},
            format="json",
        )
        self.assertEqual(invitation_response.status_code, 202)
        self.assertEqual(invitation_response.data, {"status": "invitation_sent"})
        invitation_token = re.search(
            r"(?m)^([A-Za-z0-9_-]{40,})$", mail.outbox[-1].body
        ).group(1)
        invitation = self.student_b.account_invitation
        self.assertNotIn(invitation_token, invitation.token_digest)
        self.client.force_authenticate(user=None)
        response = self.client.post(
            reverse("accounts:register"),
            {
                "invitation_token": invitation_token,
                "password": PASSWORD,
                "student_id": str(self.student_a.pk),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        linked = User.objects.get(email=self.student_b.email)
        self.assertEqual(linked.student_id, self.student_b.pk)
        self.assertTrue(linked.is_email_verified)
        invitation.refresh_from_db()
        self.assertIsNotNone(invitation.redeemed_at)
        with self.assertRaises(IntegrityError), transaction.atomic():
            type(invitation).objects.filter(pk=invitation.pk).update(redeemed_at=None)

    def test_student_cannot_provision_another_student_account(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.post(
            reverse("accounts:student-invitation-create"),
            {"student_id": str(self.student_b.pk)},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(hasattr(self.student_b, "account_invitation"))

    def test_database_prevents_student_reassignment_and_role_escalation(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.student_user.pk).update(student_id=self.student_b.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.student_user.pk).update(
                role=User.Role.ADMIN,
                is_staff=True,
            )

    def test_database_one_to_one_prevents_duplicate_student_account(self):
        duplicate = User(
            email="duplicate@btu.edu.ge",
            password=make_password("Synthetic-Passphrase-2026!"),
            student_id=self.student_a.pk,
            is_email_verified=True,
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.bulk_create([duplicate])

    def test_duplicate_account_linking_is_rejected(self):
        _, token, _ = create_student_account_invitation(
            student_id=self.student_b.pk,
            actor=self.admin,
        )
        first = redeem_student_account_invitation(token=token, password=PASSWORD)
        self.assertEqual(first.student_id, self.student_b.pk)
        with self.assertRaises(InvalidInvitation):
            redeem_student_account_invitation(token=token, password=PASSWORD)

    def test_admin_permission_not_staff_flag_controls_integration_actions(self):
        self.client.force_authenticate(user=self.student_user)
        response = self.client.get("/api/integrations/classroom/completions/")
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(user=self.admin)
        allowed = self.client.get("/api/integrations/classroom/completions/")
        self.assertEqual(allowed.status_code, 200)

    def test_password_reset_is_generic_and_changes_password(self):
        old_session = APIClient()
        logged_in = self.otp_login(self.student_a.email, client=old_session)
        self.assertEqual(logged_in.status_code, 200)
        request_url = reverse("accounts:password-reset-request")
        confirm_url = reverse("accounts:password-reset-confirm")
        unknown = self.client.post(
            request_url, {"email": "unknown@btu.edu.ge"}, format="json"
        )
        known = self.client.post(
            request_url, {"email": self.student_a.email}, format="json"
        )
        self.assertEqual(unknown.status_code, 202)
        self.assertEqual(known.status_code, 202)
        self.assertEqual(unknown.data, known.data)
        code = re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)
        response = self.client.post(
            confirm_url,
            {
                "email": self.student_a.email,
                "code": code,
                "new_password": RESET_PASSWORD,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.student_user.refresh_from_db()
        self.assertTrue(self.student_user.check_password(RESET_PASSWORD))
        self.assertEqual(old_session.get(reverse("accounts:current-user")).status_code, 403)
        replay = self.client.post(
            confirm_url,
            {
                "email": self.student_a.email,
                "code": code,
                "new_password": PASSWORD,
            },
            format="json",
        )
        self.assertEqual(replay.status_code, 400)

    def test_disabled_user_session_is_invalidated(self):
        self.otp_login(self.student_a.email)
        self.student_user.is_active = False
        self.student_user.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(reverse("accounts:current-user")).status_code, 403)

    def test_password_change_requires_current_password_and_preserves_session(self):
        self.otp_login(self.student_a.email)
        response = self.client.post(
            reverse("accounts:password-change"),
            {"current_password": PASSWORD, "new_password": RESET_PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:current-user")).status_code, 200)


class AuthCSRFApiTests(TestCase):
    def setUp(self):
        self.client = APIClient(enforce_csrf_checks=True)
        self.student = make_student("CSRF-0001", "csrf.student@btu.edu.ge")
        self.user = User.objects.create_user(
            email=self.student.email,
            password=PASSWORD,
            student=self.student,
            is_email_verified=True,
        )
        self.admin = User.objects.create_admin_user(
            email="csrf.admin@btu.edu.ge",
            password=PASSWORD,
            permission_codenames={"access_admin_api"},
        )

    def token(self):
        response = self.client.get(reverse("accounts:csrf"))
        self.assertEqual(response.status_code, 200)
        return response.json()["csrfToken"]

    def test_login_rejects_missing_csrf_and_accepts_token(self):
        url = reverse("accounts:login")
        denied = self.client.post(
            url, {"email": self.admin.email, "password": PASSWORD}, format="json"
        )
        self.assertEqual(denied.status_code, 403)
        allowed = self.client.post(
            url,
            {"email": self.admin.email, "password": PASSWORD},
            format="json",
            HTTP_X_CSRFTOKEN=self.token(),
        )
        self.assertEqual(allowed.status_code, 200)

    def test_expired_admin_session_does_not_restore_capabilities(self):
        from datetime import timedelta
        from django.contrib.sessions.models import Session
        from django.utils import timezone
        response = self.client.post(reverse('accounts:login'),
            {'email': self.admin.email, 'password': PASSWORD}, format='json',
            HTTP_X_CSRFTOKEN=self.token())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(reverse('accounts:current-user')).status_code, 200)
        cookie = self.client.cookies['sessionid'].value
        Session.objects.filter(session_key=cookie).update(expire_date=timezone.now() - timedelta(seconds=1))
        restored = APIClient(enforce_csrf_checks=True)
        restored.cookies['sessionid'] = cookie
        self.assertEqual(restored.get(reverse('accounts:current-user')).status_code, 403)

    def test_logout_flushes_session_and_password_endpoints_require_csrf(self):
        request_token = self.token()
        self.assertEqual(
            self.client.post(
                reverse("accounts:otp-request"),
                {"email": self.user.email},
                format="json",
                HTTP_X_CSRFTOKEN=request_token,
            ).status_code,
            202,
        )
        code = re.search(r"code is: ([0-9]{6})", mail.outbox[-1].body).group(1)
        login_response = self.client.post(
            reverse("accounts:otp-verify"),
            {"email": self.user.email, "code": code},
            format="json",
            HTTP_X_CSRFTOKEN=self.token(),
        )
        self.assertEqual(login_response.status_code, 200)
        denied = self.client.post(
            reverse("accounts:logout"), {}, format="json"
        )
        self.assertEqual(denied.status_code, 403)
        logged_out = self.client.post(
            reverse("accounts:logout"),
            {},
            format="json",
            HTTP_X_CSRFTOKEN=self.token(),
        )
        self.assertEqual(logged_out.status_code, 204)
        self.assertEqual(self.client.get(reverse("accounts:current-user")).status_code, 403)


class AccountLinkConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.student = make_student("LINK-0001", "link.student@btu.edu.ge")
        self.admin = User.objects.create_admin_user(
            email="link.admin@btu.edu.ge",
            password=PASSWORD,
            permission_codenames={"manage_student_accounts"},
        )

    def test_concurrent_invitation_redemption_creates_exactly_one_link(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections

        _, token, _ = create_student_account_invitation(
            student_id=self.student.pk,
            actor=self.admin,
        )
        barrier = Barrier(2)

        def redeem_once():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return redeem_student_account_invitation(token=token, password=PASSWORD)
            except InvalidInvitation:
                return None
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: redeem_once(), range(2)))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(User.objects.filter(student=self.student).count(), 1)
