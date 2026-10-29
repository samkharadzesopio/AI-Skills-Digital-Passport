import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, close_old_connections, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory

from apps.students.models import Student
from .identity import authorized_student_id, provision_student_account
from .models import LoginChallenge, LoginRateBucket, User
from .permissions import IsAdmin, IsStudent, OwnStudentProfile
from .persistent_otp import consume_login_code, request_login_code


def student(email='student@btu.edu.ge', **extra):
    return Student.objects.create(
        external_student_id=email, first_name='Test', last_name='Student',
        email=email, program='Synthetic', education_level='Bachelor',
        student_status=extra.pop('student_status', 'ACTIVE'), **extra,
    )


def issue(email='student@btu.edu.ge', ip='127.0.0.1'):
    request_login_code(email, client_ip=ip)
    return re.search(r'code is: ([0-9]{6})', mail.outbox[-1].body)[1]


class IdentityTests(TestCase):
    def setUp(self):
        self.student = student()
        self.user = provision_student_account(self.student.email)

    def test_identity_is_distinct_and_idempotent(self):
        self.assertNotEqual(self.user.pk, self.student.pk)
        self.assertEqual(authorized_student_id(self.user), self.student.pk)
        self.assertEqual(provision_student_account(' STUDENT@BTU.EDU.GE ').pk, self.user.pk)
        self.assertFalse(self.user.has_usable_password())

    def test_database_rejects_duplicate_link(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(email='other@btu.edu.ge', student=self.student)

    def test_database_rejects_case_variant_email(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create(email='STUDENT@BTU.EDU.GE')

    def test_database_rejects_student_admin(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.user.pk).update(is_staff=True)

    def test_anonymous_unlinked_inactive_and_staff_denied(self):
        unlinked = User.objects.create_user(username='unlinked', email='unlinked@btu.edu.ge')
        admin = User.objects.create_admin_user(
            email='admin@btu.edu.ge', password='Secure-Admin-Pass-2026!',
            permission_codenames={'access_admin_api'},
        )
        for user in [AnonymousUser(), unlinked, admin]:
            with self.assertRaises(PermissionDenied):
                authorized_student_id(user)
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            authorized_student_id(self.user)  # Reject even stale in-memory instances.
        with self.assertRaises(PermissionDenied):
            provision_student_account(self.student.email)

    def test_student_deactivation_and_email_change_denied(self):
        Student.objects.filter(pk=self.student.pk).update(student_status='INACTIVE')
        with self.assertRaises(PermissionDenied):
            authorized_student_id(self.user)
        Student.objects.filter(pk=self.student.pk).update(student_status='ACTIVE', email='changed@btu.edu.ge')
        with self.assertRaises(PermissionDenied):
            authorized_student_id(self.user)
        with self.assertRaises(PermissionDenied):
            provision_student_account('changed@btu.edu.ge')

    def test_never_auto_links_existing_unlinked_account(self):
        s = student('second@btu.edu.ge')
        User.objects.create_user(username='second', email=s.email)
        with self.assertRaises(PermissionDenied):
            provision_student_account(s.email)

    def test_ownership_and_role_separation(self):
        request = APIRequestFactory().get('/')
        request.user = self.user
        self.assertTrue(IsStudent().has_permission(request, None))
        self.assertFalse(IsAdmin().has_permission(request, None))
        self.assertTrue(OwnStudentProfile().has_object_permission(request, None, self.student))
        self.assertFalse(OwnStudentProfile().has_object_permission(request, None, student('other@btu.edu.ge')))
        self.assertFalse(OwnStudentProfile().has_object_permission(request, None, self.user))


class PersistentOTPTests(TestCase):
    def setUp(self):
        self.student = student()

    def consume(self, code, email='student@btu.edu.ge'):
        return consume_login_code(email, code, client_ip='127.0.0.1')

    def test_registered_student_and_single_use(self):
        code = issue()
        challenge = LoginChallenge.objects.get()
        self.assertNotIn(code, challenge.code_hash)
        self.assertEqual(challenge.expires_at - challenge.last_requested_at, timedelta(minutes=5))
        user = self.consume(code)
        self.assertEqual(user.student_id, self.student.pk)
        self.assertIsNone(self.consume(code))

    def test_unknown_inactive_non_btu_and_admin_do_not_receive_codes(self):
        student('inactive@btu.edu.ge', student_status='INACTIVE')
        User.objects.create_admin_user(
            email='admin@btu.edu.ge', password='Secure-Admin-Pass-2026!',
            permission_codenames={'access_admin_api'},
        )
        messages = []
        for address in ['unknown@btu.edu.ge', 'inactive@btu.edu.ge', 'outside@example.com', 'admin@btu.edu.ge']:
            messages.append(request_login_code(address, client_ip='127.0.0.1'))
            self.assertIsNone(self.consume('123456', address))
        self.assertFalse(getattr(mail, 'outbox', []))
        messages.append(request_login_code(self.student.email, client_ip='127.0.0.1'))
        self.assertEqual(len(set(messages)), 1)

    def test_wrong_malformed_and_bruteforce_limit(self):
        code = issue()
        for wrong in ['bad', '', '１２３４５６', None, '999999' if code != '999999' else '000000']:
            self.assertIsNone(self.consume(wrong))
        self.assertIsNone(self.consume(code))
        self.assertEqual(LoginChallenge.objects.get().attempts, 5)

    def test_expiration(self):
        code = issue()
        LoginChallenge.objects.update(expires_at=timezone.now())
        self.assertIsNone(self.consume(code))

    def test_deactivated_between_request_and_verification(self):
        code = issue()
        Student.objects.filter(pk=self.student.pk).update(student_status='INACTIVE')
        self.assertIsNone(self.consume(code))
        self.assertFalse(User.objects.exists())

    def test_delivery_failure_and_zero_delivery_fail_closed(self):
        for response in [RuntimeError('private provider error'), 0]:
            LoginChallenge.objects.all().delete()
            kwargs = {'side_effect': response} if isinstance(response, Exception) else {'return_value': response}
            with patch('apps.accounts.persistent_otp.send_mail', **kwargs):
                request_login_code(self.student.email, client_ip='127.0.0.1')
            self.assertIsNotNone(LoginChallenge.objects.get().consumed_at)

    def test_cooldown_and_hourly_request_limit(self):
        issue()
        for _ in range(10):
            request_login_code(self.student.email, client_ip='127.0.0.1')
        self.assertEqual(len(mail.outbox), 1)
        for _ in range(6):
            LoginChallenge.objects.update(last_requested_at=timezone.now() - timedelta(seconds=61))
            request_login_code(self.student.email, client_ip='127.0.0.1')
        self.assertEqual(len(mail.outbox), 5)

    def test_resend_invalidates_previous_challenge(self):
        first = issue()
        LoginChallenge.objects.update(last_requested_at=timezone.now() - timedelta(seconds=61))
        with patch('apps.accounts.persistent_otp.generate_otp', return_value='222222' if first != '222222' else '333333'):
            second = issue()
        self.assertIsNone(self.consume(first))
        self.assertIsNotNone(self.consume(second))

    def test_ip_rate_limits(self):
        issue()
        LoginRateBucket.objects.all().update(count=60)
        self.assertIsNone(self.consume('123456'))
        LoginChallenge.objects.update(last_requested_at=timezone.now() - timedelta(seconds=61))
        request_login_code(self.student.email, client_ip='127.0.0.1')
        self.assertEqual(len(mail.outbox), 1)

    def test_missing_configuration(self):
        for values in [dict(ACCOUNTS_OTP_HMAC_KEY=''), dict(ACCOUNTS_ACTIVE_STUDENT_STATUSES=[]),
                       dict(ACCOUNTS_ALLOW_TEST_EMAIL=False, EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend')]:
            with override_settings(**values), self.assertRaises(ImproperlyConfigured):
                request_login_code(self.student.email, client_ip='127.0.0.1')

    def test_sqlite_rejected_outside_explicit_test_override(self):
        from django.db import connection
        if connection.vendor == 'sqlite':
            with override_settings(ACCOUNTS_ALLOW_UNSAFE_TEST_DB=False), self.assertRaises(ImproperlyConfigured):
                issue()


class SessionTests(TestCase):
    def setUp(self):
        self.student = student()
        self.client = Client(enforce_csrf_checks=True)

    def csrf(self):
        return self.client.get('/accounts/csrf/').json()['csrfToken']

    def authenticate(self):
        old_key = self.client.session.session_key
        code = issue()
        response = self.client.post('/accounts/otp/verify/', {'email': self.student.email, 'code': code}, HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(old_key, self.client.session.session_key)

    def test_session_login_logout_and_old_cookie_invalidation(self):
        self.authenticate()
        self.assertEqual(self.client.get('/private/').json()['student_uuid'], str(self.student.pk))
        old_cookie = self.client.cookies['sessionid'].value
        self.assertEqual(self.client.post('/accounts/logout/', HTTP_X_CSRFTOKEN=self.csrf()).status_code, 204)
        attacker = Client()
        attacker.cookies['sessionid'] = old_cookie
        self.assertEqual(attacker.get('/private/').status_code, 403)

    def test_expired_database_session_cannot_restore_student_context(self):
        from django.contrib.sessions.models import Session
        self.authenticate()
        self.assertEqual(self.client.get('/accounts/me/').status_code, 200)
        cookie = self.client.cookies['sessionid'].value
        Session.objects.filter(session_key=cookie).update(expire_date=timezone.now() - timedelta(seconds=1))
        restored = Client()
        restored.cookies['sessionid'] = cookie
        self.assertEqual(restored.get('/accounts/me/').status_code, 403)
        self.assertEqual(restored.get('/private/').status_code, 403)

    def test_anonymous_private_access_denied(self):
        self.assertEqual(self.client.get('/private/').status_code, 403)

    def test_csrf_required_on_request_verify_and_logout(self):
        for endpoint in ['otp/request/', 'otp/verify/', 'logout/']:
            self.assertEqual(self.client.post('/accounts/' + endpoint, {}).status_code, 403)

    def test_session_revoked_by_student_deactivation(self):
        self.authenticate()
        Student.objects.filter(pk=self.student.pk).update(student_status='INACTIVE')
        self.assertEqual(self.client.get('/private/').status_code, 403)

    def test_session_revoked_by_account_deactivation(self):
        self.authenticate()
        User.objects.update(is_active=False)
        self.assertEqual(self.client.get('/private/').status_code, 403)

    def test_arbitrary_student_identifiers_ignored(self):
        other = student('other@btu.edu.ge')
        code = issue()
        response = self.client.post('/accounts/otp/verify/', {
            'email': self.student.email, 'code': code, 'student_id': str(other.pk),
        }, HTTP_X_CSRFTOKEN=self.csrf())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/private/').json()['student_uuid'], str(self.student.pk))

    def test_session_failure_rolls_back_otp_consumption(self):
        code = issue()
        token = self.csrf()
        with patch('django.contrib.sessions.backends.db.SessionStore.save', side_effect=RuntimeError('storage failed')):
            with self.assertRaises(RuntimeError):
                self.client.post('/accounts/otp/verify/', {'email': self.student.email, 'code': code}, HTTP_X_CSRFTOKEN=token)
        self.assertIsNone(LoginChallenge.objects.get().consumed_at)
        self.assertFalse(User.objects.exists())


class ConcurrentOTPTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_only_one_concurrent_consumer_succeeds(self):
        student()
        code = issue()
        barrier = Barrier(2)
        def consume(ip):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return consume_login_code('student@btu.edu.ge', code, client_ip=ip) is not None
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(consume, ['127.0.0.2', '127.0.0.3']))
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(User.objects.count(), 1)

class EndpointResponseTests(TestCase):
    def test_request_responses_do_not_disclose_registration_or_throttle_state(self):
        student()
        client = Client(enforce_csrf_checks=True)
        token = client.get('/accounts/csrf/').json()['csrfToken']
        responses = []
        for address in ['student@btu.edu.ge', 'missing@btu.edu.ge', 'student@btu.edu.ge', 'bad']:
            response = client.post('/accounts/otp/request/', {'email': address}, HTTP_X_CSRFTOKEN=token)
            responses.append((response.status_code, response.json()))
        self.assertTrue(all(r == responses[0] for r in responses))
        self.assertEqual(responses[0][0], 202)

    def test_student_password_cannot_use_admin_backend(self):
        from django.contrib.auth import authenticate
        s = student()
        u = provision_student_account(s.email)
        u.set_password('test-password-only')
        u.save()
        self.assertIsNone(authenticate(email=u.email, password='test-password-only'))
        admin = User.objects.create_admin_user(
            email='staff@btu.edu.ge', password='test-password-only',
            permission_codenames={'access_admin_api'},
        )
        self.assertEqual(authenticate(email=admin.email, password='test-password-only'), admin)

    @override_settings(SECRET_KEY='django-insecure-do-not-use')
    def test_scaffold_secret_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            request_login_code('student@btu.edu.ge', client_ip='127.0.0.1')

class ConcurrentAttemptTests(TransactionTestCase):
    @skipUnlessDBFeature('has_select_for_update')
    def test_parallel_wrong_codes_cannot_exceed_attempt_budget(self):
        student()
        code = issue()
        wrong = '999999' if code != '999999' else '000000'
        barrier = Barrier(8)
        def consume(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return consume_login_code('student@btu.edu.ge', wrong, client_ip=f'127.0.0.{index + 2}')
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(list(pool.map(consume, range(8))), [None] * 8)
        self.assertEqual(LoginChallenge.objects.get().attempts, 5)
        self.assertIsNone(consume_login_code('student@btu.edu.ge', code, client_ip='127.0.0.1'))

    @skipUnlessDBFeature('has_select_for_update')
    def test_parallel_first_requests_send_once(self):
        student()
        barrier = Barrier(2)
        def request(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return request_login_code('student@btu.edu.ge', client_ip=f'127.0.0.{index + 2}')
            finally:
                close_old_connections()
        with patch('apps.accounts.persistent_otp.send_mail', return_value=1) as send:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(request, range(2)))
            self.assertEqual(results[0], results[1])
            self.assertEqual(send.call_count, 1)
        self.assertEqual(LoginChallenge.objects.get().request_count, 1)

class LoginPayloadTests(TestCase):
    def test_non_object_json_is_rejected_without_issuing_or_consuming_codes(self):
        client = Client(enforce_csrf_checks=True)
        token = client.get('/accounts/csrf/').json()['csrfToken']
        for endpoint in ['request', 'verify']:
            for payload in [[], ['email'], 'student@btu.edu.ge', 123, None]:
                with self.subTest(endpoint=endpoint, payload=payload):
                    import json
                    response = client.post(
                        f'/accounts/otp/{endpoint}/', json.dumps(payload),
                        content_type='application/json', HTTP_X_CSRFTOKEN=token,
                    )
                    self.assertEqual(response.status_code, 400)
        self.assertFalse(LoginChallenge.objects.exists())
        self.assertFalse(LoginRateBucket.objects.exists())

    def test_rate_window_uses_time_after_lock_wait(self):
        from .persistent_otp import digest, take_rate
        from django.conf import settings
        key = settings.ACCOUNTS_OTP_HMAC_KEY.encode()
        before = timezone.now()
        bucket_key = digest(key, 'test-window', '127.0.0.1')
        LoginRateBucket.objects.create(
            key=bucket_key, window_started_at=before, count=30,
        )
        after = before + timedelta(hours=1, seconds=1)
        with patch('apps.accounts.persistent_otp.timezone.now', return_value=after):
            self.assertTrue(take_rate(key, 'test-window', '127.0.0.1', before, 30))
        bucket = LoginRateBucket.objects.get(pk=bucket_key)
        self.assertEqual(bucket.count, 1)
        self.assertEqual(bucket.window_started_at, after)
