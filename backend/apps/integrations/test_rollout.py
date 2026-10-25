from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from apps.accounts.models import DeferredMail, SecurityAudit
from apps.credentials.models import CredentialIssuer


@override_settings(DEBUG=False, ACCOUNTS_ALLOW_TEST_EMAIL=False, ACCOUNTS_ALLOW_UNSAFE_TEST_DB=False,
                   SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True, SECURE_SSL_REDIRECT=True,
                   EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend', EMAIL_HOST='smtp.invalid',
                   EMAIL_USE_TLS=True, BTU_CLASSROOM_ISSUER_REFERENCE='ROLLOUT-SYNTHETIC',
                   VERIFICATION_TRUSTED_ISSUER_REFERENCES=['ROLLOUT-SYNTHETIC'], BTU_AUTHORIZED_COMPLETION_SOURCES=[])
class PreflightTests(TestCase):
    def setUp(self):
        CredentialIssuer.objects.create(reference='ROLLOUT-SYNTHETIC', display_name='Synthetic institution')

    def test_preflight_is_read_only(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as queries:
            call_command('deployment_preflight', stdout=StringIO())
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'ALTER', 'CREATE', 'DROP')) for q in queries))

    def test_policy_and_security_failures_are_actionable(self):
        for values in [dict(BTU_CLASSROOM_ISSUER_REFERENCE=''), dict(VERIFICATION_TRUSTED_ISSUER_REFERENCES=[]),
                       dict(ACCOUNTS_ALLOW_TEST_EMAIL=True), dict(SESSION_COOKIE_SECURE=False),
                       dict(BTU_AUTHORIZED_COMPLETION_SOURCES=['FORGED'])]:
            with self.subTest(values=values), override_settings(**values), self.assertRaises(CommandError):
                call_command('deployment_preflight', stdout=StringIO())

    @override_settings(BTU_AUTHORIZED_COMPLETION_SOURCES=['BTU_GOOGLE_SHEETS'], BTU_GOOGLE_SHEET_ID='', GOOGLE_SERVICE_ACCOUNT_FILE='')
    def test_missing_google_credentials_deny_readiness(self):
        with self.assertRaises(CommandError):
            call_command('deployment_preflight', stdout=StringIO())

    def test_missing_issuer_does_not_auto_provision(self):
        CredentialIssuer.objects.all().delete()
        with self.assertRaises(CommandError):
            call_command('deployment_preflight', stdout=StringIO())
        self.assertFalse(CredentialIssuer.objects.exists())


class WorkerAndRetentionTests(TestCase):
    @patch('apps.accounts.management.commands.run_backend_workers.call_command')
    @patch('apps.accounts.management.commands.run_backend_workers.deliver_one', return_value=False)
    def test_worker_cycle_polls_recovery_and_cleanup_without_mock_ingestion(self, deliver, command):
        call_command('run_backend_workers', once=True, stdout=StringIO())
        self.assertEqual([c.args[0] for c in command.call_args_list],
                         ['retry_classroom_events', 'reconcile_import_runs', 'purge_expired_auth_state', 'clearsessions'])
        deliver.assert_called_once()

    @patch('apps.accounts.management.commands.run_backend_workers.deliver_one', side_effect=RuntimeError('private provider detail'))
    def test_worker_failure_is_sanitized(self, deliver):
        with self.assertRaises(CommandError) as error:
            call_command('run_backend_workers', once=True, stdout=StringIO())
        self.assertNotIn('private provider', str(error.exception))

    def test_queue_and_audit_retention_preserves_recent_records(self):
        old = DeferredMail.objects.create(recipient='old@btu.edu.ge', purpose='LOGIN', client_ip='unknown', requested_at=timezone.now()-timedelta(days=2))
        recent = DeferredMail.objects.create(recipient='recent@btu.edu.ge', purpose='LOGIN', client_ip='unknown')
        audit = SecurityAudit.objects.create(action='OLD', ip_digest='a'*64)
        SecurityAudit.objects.filter(pk=audit.pk).update(created_at=timezone.now()-timedelta(days=31))
        active = SecurityAudit.objects.create(action='RECENT', ip_digest='b'*64)
        call_command('purge_expired_auth_state', stdout=StringIO())
        self.assertFalse(DeferredMail.objects.filter(pk=old.pk).exists())
        self.assertTrue(DeferredMail.objects.filter(pk=recent.pk).exists())
        self.assertFalse(SecurityAudit.objects.filter(pk=audit.pk).exists())
        self.assertTrue(SecurityAudit.objects.filter(pk=active.pk).exists())
