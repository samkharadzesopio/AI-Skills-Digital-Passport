from datetime import timedelta
from unittest.mock import patch
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from apps.students.models import Student
from .models import DeferredMail, SecurityAudit, LoginChallenge, User
from .mail_queue import deliver_one
from .persistent_otp import request_login_code, consume_login_code


@override_settings(ACCOUNTS_ALLOW_TEST_EMAIL=False, SESSION_COOKIE_SECURE=True,
                   CSRF_COOKIE_SECURE=True, SESSION_ENGINE='django.contrib.sessions.backends.db',
                   EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
                   EMAIL_HOST='smtp.invalid', EMAIL_USE_TLS=True)
class MailQueueTests(TransactionTestCase):
    def setUp(self):
        Student.objects.create(external_student_id='QUEUE-TEST', first_name='Test', last_name='Student',
                               email='queue@btu.edu.ge', program='AI', education_level='Bachelor', student_status='Active')

    def test_request_enqueues_without_delivery_or_eligibility_lookup(self):
        with patch('apps.accounts.persistent_otp.send_mail') as send, patch('apps.accounts.persistent_otp.eligible', side_effect=AssertionError('must defer lookup')):
            known = request_login_code('queue@btu.edu.ge', client_ip='127.0.0.1')
            unknown = request_login_code('unknown@btu.edu.ge', client_ip='127.0.0.1')
            self.assertEqual(known, unknown)
            send.assert_not_called()
        self.assertEqual(DeferredMail.objects.count(), 2)
        self.assertFalse(LoginChallenge.objects.exists())
        self.assertFalse(any('code' in f.name or 'message' in f.name for f in DeferredMail._meta.fields if f.name != 'error_code'))

    def test_worker_delivery_activates_single_use_code_outside_transaction(self):
        request_login_code('queue@btu.edu.ge', client_ip='127.0.0.1')
        codes = []
        def send(*args, **kwargs):
            self.assertFalse(connection.in_atomic_block)
            codes.append(args[1].split('code is: ')[1][:6])
            return 1
        with patch('apps.accounts.persistent_otp.send_mail', side_effect=send):
            self.assertTrue(deliver_one())
        self.assertEqual(DeferredMail.objects.get().state, 'SENT')
        self.assertIsNotNone(consume_login_code('queue@btu.edu.ge', codes[0], client_ip='127.0.0.1'))
        self.assertIsNone(consume_login_code('queue@btu.edu.ge', codes[0], client_ip='127.0.0.1'))
        self.assertFalse(deliver_one())

    def test_failed_delivery_recovers_with_bounded_attempts(self):
        request_login_code('queue@btu.edu.ge', client_ip='127.0.0.1')
        with patch('apps.accounts.persistent_otp.send_mail', side_effect=RuntimeError('private SMTP detail')):
            self.assertTrue(deliver_one())
        row = DeferredMail.objects.get()
        self.assertEqual(row.state, 'PENDING')
        self.assertEqual(row.error_code, 'DELIVERY_FAILED')
        self.assertIsNotNone(LoginChallenge.objects.get().consumed_at)
        DeferredMail.objects.update(next_attempt_at=timezone.now())
        LoginChallenge.objects.update(last_requested_at=timezone.now() - timedelta(seconds=61))
        with patch('apps.accounts.persistent_otp.send_mail', return_value=1):
            self.assertTrue(deliver_one())
        self.assertEqual(DeferredMail.objects.get().state, 'SENT')

    def test_unknown_recipient_skips_delivery_and_expired_jobs_fail(self):
        request_login_code('unknown@btu.edu.ge', client_ip='127.0.0.1')
        with patch('apps.accounts.persistent_otp.send_mail') as send:
            deliver_one()
            send.assert_not_called()
        request_login_code('queue@btu.edu.ge', client_ip='127.0.0.1')
        DeferredMail.objects.filter(recipient='queue@btu.edu.ge').update(requested_at=timezone.now() - timedelta(minutes=6))
        deliver_one()
        self.assertEqual(DeferredMail.objects.get(recipient='queue@btu.edu.ge').error_code, 'EXPIRED')

    def test_reset_is_queued_and_failed_third_lease_is_recovered(self):
        from .services import request_password_reset
        request_password_reset(email='queue@btu.edu.ge', ip_address='127.0.0.1')
        self.assertEqual(DeferredMail.objects.get().purpose, 'RESET')
        DeferredMail.objects.update(state='SENDING', attempts=3, lease_expires_at=timezone.now() - timedelta(seconds=1))
        self.assertTrue(deliver_one())
        self.assertEqual(DeferredMail.objects.get().state, 'FAILED')


class AuditTests(TransactionTestCase):
    def test_unauthorized_action_records_safe_outcome(self):
        client = APIClient()
        response = client.post('/api/integrations/classroom/sync/', {'secret': 'do-not-store'}, format='json')
        self.assertEqual(response.status_code, 403)
        row = SecurityAudit.objects.get()
        self.assertEqual(row.status_code, 403)
        self.assertEqual(len(row.ip_digest), 64)
        self.assertNotIn('do-not-store', str(row.__dict__))
        self.assertIsNone(row.actor_id)
        self.assertEqual(response['Cache-Control'], 'no-store')
