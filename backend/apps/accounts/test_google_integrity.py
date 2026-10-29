from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.sessions.backends.db import SessionStore
from django.db import close_old_connections, connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from .google_auth import GoogleProblem, finish
from .models import GoogleLoginChallenge
from .otp_utils import security_digest


@override_settings(GOOGLE_OAUTH_CLIENT_ID='123456789-synthetic.apps.googleusercontent.com')
class GoogleNonceConcurrencyTests(TransactionTestCase):
    def test_two_simultaneous_submissions_consume_only_once(self):
        session = SessionStore(); session.create()
        challenge = GoogleLoginChallenge.objects.create(nonce_digest='a' * 64,
            session_digest=security_digest('google.session', session.session_key), intent='login',
            audience='123456789-synthetic.apps.googleusercontent.com', expires_at=timezone.now() + timedelta(minutes=5))
        barrier = Barrier(2)
        def submit():
            close_old_connections()
            try:
                request = SimpleNamespace(session=SessionStore(session.session_key), user=None, META={'REMOTE_ADDR': '127.0.0.1'})
                barrier.wait(timeout=10)
                try:
                    finish(request, str(challenge.pk), 'synthetic-token')
                    return 'PORTAL_AUTHENTICATED'
                except GoogleProblem as error:
                    return error.code
            finally:
                close_old_connections()
        with patch('apps.accounts.google_auth.verify_credential', return_value=('unlinked-subject', 'synthetic@btu.edu.ge')) as verifier:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: submit(), range(2)))
        self.assertCountEqual(results, ['PORTAL_AUTHENTICATED', 'GOOGLE_INVALID_CHALLENGE'])
        self.assertEqual(verifier.call_count, 1)


class GoogleMigrationTests(TransactionTestCase):
    def test_additive_migration_preserves_existing_institutional_account(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([('accounts', '0007_alter_user_options')])
            old = executor.loader.project_state([('accounts', '0007_alter_user_options')]).apps
            Student = old.get_model('students', 'Student')
            User = old.get_model('accounts', 'User')
            student = Student.objects.create(external_student_id='SYNTHETIC-MIGRATION-OAUTH', first_name='Synthetic',
                last_name='Migration', email='migration.synthetic@btu.edu.ge', program='AI',
                education_level='Bachelor', student_status='ACTIVE')
            user = User.objects.create(email=student.email, student_id=student.pk, role='STUDENT',
                is_active=True, is_email_verified=True, is_staff=False, is_superuser=False, password='!')
            executor = MigrationExecutor(connection)
            executor.migrate(leaves)
            new = executor.loader.project_state(leaves).apps
            restored = new.get_model('accounts', 'User').objects.get(pk=user.pk)
            self.assertEqual((restored.student_id, restored.email, restored.role), (student.pk, student.email, 'STUDENT'))
            self.assertFalse(new.get_model('accounts', 'GoogleIdentity').objects.exists())
            self.assertEqual(new.get_model('students', 'Student').objects.get(pk=student.pk).external_student_id, 'SYNTHETIC-MIGRATION-OAUTH')
        finally:
            MigrationExecutor(connection).migrate(leaves)
