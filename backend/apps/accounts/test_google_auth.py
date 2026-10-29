"""Actual signature/claim checks against synthetic keys; never contacts Google."""
import json
import re
import time
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.sessions.models import Session
from django.core import mail
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.db import DatabaseError, IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from google.auth import crypt, jwt
from rest_framework.test import APIClient

from apps.students.models import Student
from .google_auth import GoogleCertificates, GoogleProblem
from .models import GoogleIdentity, GoogleLoginChallenge, PortalStudentMapping, SecurityAudit, User

CLIENT_ID = '123456789-synthetic.apps.googleusercontent.com'


@override_settings(ROOT_URLCONF='config.urls', GOOGLE_OAUTH_CLIENT_ID=CLIENT_ID,
                   ACCOUNTS_ACTIVE_STUDENT_STATUSES=['ACTIVE'])
class GoogleAuthTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        cls.signer = crypt.RSASigner.from_string(private, key_id='synthetic-key')
        cls.public_key = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()

    def setUp(self):
        self.student = Student.objects.create(external_student_id='SYNTHETIC-OAUTH-STUDENT',
            first_name='Synthetic', last_name='OAuth', email='synthetic.oauth@btu.edu.ge',
            program='AI', education_level='Bachelor', student_status='ACTIVE')
        self.provider = self.enterContext(patch('apps.accounts.google_auth.certificate_request',
            return_value=SimpleNamespace(status=200, data=json.dumps({'synthetic-key': self.public_key}).encode())))
        # Any unintended Google HTTP request fails the suite immediately.
        self.enterContext(patch('requests.sessions.Session.request', side_effect=AssertionError('No live Google')))
        self.client = APIClient(enforce_csrf_checks=True)

    def post(self, path, data, client=None):
        client = client or self.client
        csrf = client.get('/api/accounts/csrf/').json()['csrfToken']
        return client.post('/api/accounts/' + path + '/', data, format='json', HTTP_X_CSRFTOKEN=csrf)

    def otp(self, client=None):
        client = client or self.client
        self.assertEqual(self.post('otp/request', {'email': self.student.email}, client).status_code, 202)
        code = re.search(r'code is: ([0-9]{6})', mail.outbox[-1].body)[1]
        self.assertEqual(self.post('otp/verify', {'email': self.student.email, 'code': code}, client).status_code, 200)
        return User.objects.get(student=self.student)

    def challenge(self, intent='login', client=None):
        response = self.post('google/challenge', {'intent': intent}, client)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def token(self, nonce_value, **changes):
        claims = {'iss': 'https://accounts.google.com', 'aud': CLIENT_ID, 'sub': 'synthetic-google-subject',
            'email': self.student.email, 'email_verified': True, 'hd': 'btu.edu.ge',
            'nonce': nonce_value, 'iat': int(time.time()) - 1, 'exp': int(time.time()) + 300}
        claims.update(changes)
        return jwt.encode(self.signer, claims).decode()

    def authenticate(self, challenge, token=None, client=None):
        return self.post('google/authenticate', {'challenge_id': challenge['challenge_id'],
            'credential': token or self.token(challenge['nonce'])}, client)

    def link(self):
        user = self.otp()
        self.assertEqual(self.authenticate(self.challenge('link')).status_code, 200)
        return user

    def test_initial_link_requires_real_fresh_otp_and_preserves_official_records(self):
        self.assertEqual(self.post('google/challenge', {'intent': 'link'}).status_code, 403)
        before = list(Student.objects.values())
        user = self.link()
        identity = GoogleIdentity.objects.get()
        self.assertEqual(identity.user_id, user.pk)
        self.assertEqual(identity.subject, 'synthetic-google-subject')
        self.assertEqual(list(Student.objects.values()), before)
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertNotIn('google_link_otp', self.client.session)

    def test_linked_google_login_rotates_session_has_no_otp_link_privilege_and_logout_denies(self):
        user = self.link()
        self.assertEqual(self.post('logout', {}).status_code, 204)
        challenge = self.challenge()
        old_key = self.client.session.session_key
        result = self.authenticate(challenge)
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()['linked'])
        self.assertEqual(self.client.get('/api/accounts/me/').json()['role'], 'STUDENT')
        self.assertNotEqual(old_key, self.client.session.session_key)
        self.assertFalse(Session.objects.filter(session_key=old_key).exists())
        self.assertEqual(self.post('google/challenge', {'intent': 'link'}).status_code, 403)
        self.assertEqual(User.objects.get(pk=user.pk).student_id, self.student.pk)
        self.assertEqual(self.post('logout', {}).status_code, 204)
        self.assertEqual(self.client.get('/api/accounts/me/').status_code, 403)

    def test_unlinked_valid_token_creates_independent_empty_portal_not_academic_records(self):
        before = list(Student.objects.values())
        response = self.authenticate(self.challenge())
        self.assertEqual(response.status_code, 200, response.content)
        user = User.objects.get()
        self.assertTrue(user.portal_only)
        self.assertIsNone(user.student_id)
        self.assertFalse(user.has_usable_password() or user.is_staff or user.is_superuser)
        self.assertEqual(list(Student.objects.values()), before)
        self.assertEqual(response.json()['account']['student_association'], 'unlinked')
        self.assertTrue(response.json()['account']['portal_access'])
        self.assertEqual(self.client.get('/api/accounts/portal/').json(),
            {'email': self.student.email, 'records_linked': False, 'mapping_pending': True})
        for path in ('dashboard', 'skills', 'achievements', 'credentials', 'passport', 'passport/versions'):
            self.assertEqual(self.client.get('/api/student/' + path + '/').status_code, 403, path)
        self.assertEqual(self.client.get('/api/admin/students/').status_code, 403)

    def test_unprovisioned_workspace_email_has_empty_portal_access(self):
        challenge = self.challenge()
        response = self.authenticate(challenge, self.token(challenge['nonce'], email='unknown@btu.edu.ge'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.get().portal_only)
        self.assertEqual(Student.objects.count(), 1)

    def test_repeat_subject_restores_same_portal(self):
        self.assertEqual(self.authenticate(self.challenge()).status_code, 200)
        user = GoogleIdentity.objects.get().user
        self.post('logout', {})
        self.assertEqual(self.authenticate(self.challenge()).status_code, 200)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(str(user.pk), self.client.session['_auth_user_id'])

    def test_recycled_email_is_separate_from_legacy_and_other_subjects(self):
        legacy = self.otp(); self.post('logout', {})
        self.assertEqual(self.authenticate(self.challenge()).status_code, 200)
        first = GoogleIdentity.objects.get().user
        self.assertNotEqual(first.pk, legacy.pk)
        self.assertIsNone(first.student_id)
        self.post('logout', {})
        challenge = self.challenge()
        self.assertEqual(self.authenticate(challenge, self.token(challenge['nonce'], sub='new-owner-sub')).status_code, 200)
        second = GoogleIdentity.objects.get(subject='new-owner-sub').user
        self.assertNotEqual(first.pk, second.pk)
        self.assertIsNone(second.student_id)
        self.assertEqual(User.objects.get_by_natural_key(self.student.email).pk, legacy.pk)
        self.assertEqual(self.client.get('/api/student/passport/').status_code, 403)

    def test_workspace_member_with_admin_email_gets_no_administrator_privileges(self):
        password = 'Synthetic-admin-secret-123'
        admin = User.objects.create_admin_user(email='admin.portal@btu.edu.ge', password=password,
            permission_codenames={'view_student_records'})
        challenge = self.challenge()
        self.assertEqual(self.authenticate(challenge, self.token(challenge['nonce'], email=admin.email)).status_code, 200)
        self.assertEqual(self.client.get('/api/accounts/me/').json()['role'], 'STUDENT')
        self.assertEqual(self.client.get('/api/admin/students/').status_code, 403)
        self.post('logout', {})
        self.assertEqual(self.post('login', {'email': admin.email, 'password': password}).status_code, 200)
        self.assertEqual(self.client.get('/api/accounts/me/').json()['role'], 'ADMIN')

    def test_approved_mapping_uses_institutional_id_and_resolves_future_records(self):
        from .portal import approve_mapping
        from rest_framework.exceptions import PermissionDenied
        self.authenticate(self.challenge())
        identity = GoogleIdentity.objects.get()
        with self.assertRaises((PermissionDenied, DjangoPermissionDenied)):
            approve_mapping(actor=identity.user, subject=identity.subject, external_student_id='FUTURE-PORTAL-ID', approval_reference='Synthetic approval')
        admin = User.objects.create_admin_user(email='mapping.admin@btu.edu.ge', password='Synthetic-admin-secret-123',
            permission_codenames={'manage_student_accounts'})
        mapping = approve_mapping(actor=admin, subject=identity.subject, external_student_id='FUTURE-PORTAL-ID', approval_reference='Synthetic approved identity record')
        self.assertEqual(self.client.get('/api/accounts/me/').json()['student_association'], 'unlinked')
        future = Student.objects.create(external_student_id='FUTURE-PORTAL-ID', first_name='Future', last_name='Alumni',
            email='different.record@btu.edu.ge', program='AI', education_level='Bachelor', student_status='ALUMNI')
        self.assertEqual(self.client.get('/api/accounts/me/').json()['student_association'], 'linked')
        from .authorization import get_authenticated_student_id
        from .authentication import GoogleWorkspaceBackend
        self.assertEqual(get_authenticated_student_id(GoogleWorkspaceBackend().get_user(identity.user_id)), future.pk)
        self.assertEqual(self.client.get('/api/student/dashboard/').status_code, 200)
        with self.assertRaises(DatabaseError), transaction.atomic():
            PortalStudentMapping.objects.filter(pk=mapping.pk).update(external_student_id=self.student.external_student_id)
        self.assertTrue(SecurityAudit.objects.filter(action='PortalStudentMapping:APPROVED', actor=admin).exists())

    def test_mapping_conflicts_cannot_reassign_historical_google_owner(self):
        from .portal import approve_mapping
        owner = self.link(); self.post('logout', {})
        challenge = self.challenge()
        self.authenticate(challenge, self.token(challenge['nonce'], sub='another-portal'))
        admin = User.objects.create_admin_user(email='mapping.admin@btu.edu.ge', password='Synthetic-admin-secret-123',
            permission_codenames={'manage_student_accounts'})
        with self.assertRaises(ValueError):
            approve_mapping(actor=admin, subject='another-portal', external_student_id=self.student.external_student_id, approval_reference='Conflict rejected')
        self.assertEqual(GoogleIdentity.objects.get(subject='synthetic-google-subject').user_id, owner.pk)
        self.assertFalse(PortalStudentMapping.objects.exists())

    def test_signature_and_security_claims_are_cryptographically_checked(self):
        changes = [{'aud': 'other.apps.googleusercontent.com'}, {'iss': 'https://evil.invalid'},
            {'exp': int(time.time()) - 1}, {'email_verified': False}, {'email_verified': 'true'},
            {'email': 'outsider@gmail.com'}, {'email': 'student@btu.edu.ge.evil.invalid'},
            {'hd': None}, {'hd': 'other.edu.ge'}, {'nonce': 'wrong'}, {'sub': ''}, {'azp': 'other-client'}]
        for claims in changes:
            client = APIClient(enforce_csrf_checks=True)
            with self.subTest(claims=claims):
                challenge = self.challenge(client=client)
                response = self.authenticate(challenge, self.token(challenge['nonce'], **claims), client)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()['code'], 'GOOGLE_INVALID_TOKEN')
        challenge = self.challenge()
        token = self.token(challenge['nonce'])
        payload, signature = token.rsplit('.', 1)
        wrong = payload + '.' + ('A' if signature[0] != 'A' else 'B') + signature[1:]
        self.assertEqual(self.authenticate(challenge, wrong).status_code, 400)
        self.assertFalse(GoogleIdentity.objects.exists())

    def test_nonce_is_one_use_even_after_invalid_token(self):
        challenge = self.challenge()
        self.assertEqual(self.authenticate(challenge, 'invalid-token').status_code, 400)
        self.assertEqual(self.authenticate(challenge).json()['code'], 'GOOGLE_INVALID_CHALLENGE')
        self.assertIsNotNone(GoogleLoginChallenge.objects.get(pk=challenge['challenge_id']).consumed_at)

    def test_challenge_cannot_move_to_another_browser_or_be_used_after_expiry(self):
        challenge = self.challenge()
        other = APIClient(enforce_csrf_checks=True)
        self.assertEqual(self.authenticate(challenge, client=other).json()['code'], 'GOOGLE_INVALID_CHALLENGE')
        GoogleLoginChallenge.objects.filter(pk=challenge['challenge_id']).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.authenticate(challenge).json()['code'], 'GOOGLE_INVALID_CHALLENGE')

    def test_csrf_is_required_for_challenge_and_authentication_before_provider_access(self):
        for path, data in [('google/challenge', {'intent': 'login'}),
                           ('google/authenticate', {'challenge_id': 'invalid', 'credential': 'invalid'})]:
            response = self.client.post('/api/accounts/' + path + '/', data, format='json')
            self.assertEqual(response.status_code, 403)
        self.provider.assert_not_called()

    def test_existing_non_otp_session_or_stale_otp_cannot_link(self):
        user = self.otp()
        session = self.client.session
        session.pop('google_link_otp'); session.save()
        self.assertEqual(self.post('google/challenge', {'intent': 'link'}).json()['code'], 'GOOGLE_FRESH_OTP_REQUIRED')
        session = self.client.session
        session['google_link_otp'] = {'user_id': str(user.pk), 'at': time.time() - 301}; session.save()
        self.assertEqual(self.post('google/challenge', {'intent': 'link'}).status_code, 403)

    def test_conflicts_and_database_uniqueness_fail_closed(self):
        user = self.otp()
        GoogleIdentity.objects.create(user=user, subject='already-linked')
        self.assertEqual(self.authenticate(self.challenge('link')).status_code, 409)
        with self.assertRaises(IntegrityError), transaction.atomic():
            GoogleIdentity.objects.create(user=user, subject='different')
        with self.assertRaises(DatabaseError), transaction.atomic():
            GoogleIdentity.objects.filter(user=user).update(subject='reassigned')
        self.assertEqual(GoogleIdentity.objects.get().subject, 'already-linked')

    def test_google_cannot_link_or_login_an_administrator(self):
        admin = User.objects.create_admin_user(email='synthetic.admin@btu.edu.ge', password='Synthetic-admin-secret-123',
            permission_codenames={'view_student_records'})
        self.assertEqual(self.post('login', {'email': admin.email, 'password': 'Synthetic-admin-secret-123'}).status_code, 200)
        self.assertEqual(self.post('google/challenge', {'intent': 'link'}).status_code, 403)
        self.assertEqual(self.post('google/challenge', {'intent': 'login'}).status_code, 403)
        with self.assertRaises(DatabaseError), transaction.atomic():
            GoogleIdentity.objects.create(user=admin, subject='admin-subject')
        self.assertEqual(self.client.get('/api/accounts/me/').json()['role'], 'ADMIN')
        self.assertEqual(self.post('logout', {}).status_code, 204)

    def test_alumni_can_restore_trusted_records_but_disabled_account_is_rejected(self):
        user = self.link()
        self.post('logout', {})
        self.student.student_status = 'INACTIVE'; self.student.save(update_fields=['student_status'])
        self.assertEqual(self.authenticate(self.challenge()).status_code, 200)
        self.assertEqual(self.client.get('/api/student/dashboard/').status_code, 200)
        self.post('logout', {})
        self.student.student_status = 'ACTIVE'; self.student.save(update_fields=['student_status'])
        User.objects.filter(pk=user.pk).update(is_active=False)
        self.assertEqual(self.authenticate(self.challenge()).status_code, 403)

    def test_changed_email_does_not_reassign_google_subject(self):
        self.link(); self.post('logout', {})
        challenge = self.challenge()
        self.assertEqual(self.authenticate(challenge, self.token(challenge['nonce'], email='different@btu.edu.ge')).status_code, 200)
        self.assertEqual(GoogleIdentity.objects.get().subject, 'synthetic-google-subject')

    def test_expired_django_session_cannot_link_and_student_route_is_denied(self):
        self.link()
        Session.objects.filter(session_key=self.client.session.session_key).update(expire_date=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get('/api/student/passport/').status_code, 403)
        self.assertEqual(self.post('google/challenge', {'intent': 'link'}).status_code, 403)

    def test_disabled_configuration_and_rate_limit_never_contact_provider(self):
        with self.settings(GOOGLE_OAUTH_CLIENT_ID=''):
            self.assertEqual(self.post('google/challenge', {'intent': 'login'}).status_code, 503)
        for _ in range(10):
            self.challenge()
        response = self.post('google/challenge', {'intent': 'login'})
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
        self.provider.assert_not_called()

    def test_audit_contains_no_credential_nonce_email_or_subject(self):
        challenge = self.challenge()
        token = self.token(challenge['nonce'])
        self.authenticate(challenge, token)
        audit = json.dumps(list(SecurityAudit.objects.values()), default=str)
        for value in (token, challenge['nonce'], self.student.email, 'synthetic-google-subject'):
            self.assertNotIn(value, audit)
        self.assertTrue(SecurityAudit.objects.filter(action__startswith='Google', status_code=200).exists())

    def test_certificate_transport_refuses_arbitrary_endpoints(self):
        with self.assertRaises(GoogleProblem):
            GoogleCertificates()('https://evil.invalid/keys')

    def test_audience_change_after_challenge_is_rejected(self):
        challenge = self.challenge()
        with self.settings(GOOGLE_OAUTH_CLIENT_ID='other.apps.googleusercontent.com'):
            self.assertEqual(self.authenticate(challenge).json()['code'], 'GOOGLE_INVALID_CHALLENGE')
