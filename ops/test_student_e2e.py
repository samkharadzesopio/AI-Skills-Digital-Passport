"""Real React -> Vite proxy -> Django -> disposable PostgreSQL acceptance.

Uses local-only test settings, synthetic fixtures and local-memory email. Never
imports production settings/.env. Requires the existing frontend npm dependencies.
Run with the local PostgreSQL variables documented in STUDENT_INTEGRATION.md.
"""
import contextvars
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
from datetime import timedelta
from wsgiref.simple_server import make_server, WSGIRequestHandler, WSGIServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'apps.integrations.postgres_test_settings'
os.environ['INTEGRATION_TEST_DB_NAME'] = 'test_student_frontend_e2e'
# The imported test settings enforce an explicitly configured loopback DB.
import django
django.setup()
from django.conf import settings
from django.core import mail
from django.core.wsgi import get_wsgi_application
from django.db import connections
from django.test.utils import setup_databases, teardown_databases
from django.utils import timezone
from apps.api.test_pdf import PassportPDFAPITests
from apps.credentials.services import revoke_credential
from apps.passports.models import PassportDocument

settings.ROOT_URLCONF = 'config.urls'
settings.ALLOWED_HOSTS = ['localhost', '127.0.0.1']
settings.CREDENTIAL_REVOCATION_AUTHORIZER = 'apps.accounts.authorization.authorize_credential_revocation'


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


class IsolatedServer(WSGIServer):
    allow_reuse_address = False


db = setup_databases(verbosity=0, interactive=False)
fixture = PassportPDFAPITests()
server = None
try:
    fixture.setUp()
    fixture.issue(fixture.student, issued_at=timezone.now() - timedelta(days=2), expires_at=timezone.now() - timedelta(days=1))
    revoked = fixture.issue(fixture.student)
    revoke_credential(public_reference=revoked.public_reference, actor=fixture.admin, reason='Synthetic student acceptance revocation')
    fixture.issue(fixture.student)
    other_credential = fixture.issue(fixture.other)
    fixture.passport.refresh_from_db()
    latest = fixture.passport.latest_version
    with tempfile.TemporaryDirectory(prefix='student-ui-http-') as directory:
        artifact = Path(directory)
        # Only synthetic test mail is mirrored for the local test driver. No HTTP
        # endpoint exposes OTPs, fixtures, credentials or test control operations.
        from django.core.mail.backends.locmem import EmailBackend

        class TestMailbox(EmailBackend):
            def send_messages(self, messages):
                result = super().send_messages(messages)
                for message in messages:
                    match = re.search(r'code is: ([0-9]{6})', message.body)
                    if match:
                        for recipient in message.to:
                            (artifact / (recipient.replace('@', '_') + '.otp')).write_text(match.group(1))
                return result

        # Register the test-only backend in this harness module, not application code.
        settings.EMAIL_BACKEND = '__main__.TestMailbox'
        metadata = {
            'email': fixture.user.email,
            'otherEmail': fixture.other_user.email,
            'credentialId': str(fixture.credential.pk),
            'credentialReference': str(fixture.credential.public_reference),
            'otherCredentialId': str(other_credential.pk),
            'passportReference': str(fixture.passport.public_reference),
            'latestVersionId': str(latest.pk),
            'historicalVersionId': str(fixture.version.pk),
            'latestVersionReference': str(latest.public_reference),
            'historicalVersionReference': str(fixture.version.public_reference),
        }
        server = make_server('127.0.0.1', 0, get_wsgi_application(), server_class=IsolatedServer, handler_class=QuietHandler)
        context = contextvars.copy_context()
        threading.Thread(target=lambda: context.run(server.serve_forever), daemon=True).start()
        env = {**os.environ, 'BTU_DEV_API_TARGET': f'http://127.0.0.1:{server.server_port}', 'BTU_E2E_FIXTURE': json.dumps(metadata), 'BTU_E2E_MAILBOX': str(artifact), 'VITE_ENABLE_DEMO': 'false'}
        result = subprocess.run(['node', 'scripts/check-student-http.mjs'], cwd=ROOT / 'frontend', env=env, timeout=180)
        if result.returncode:
            raise RuntimeError(f'Real Student UI/HTTP acceptance failed with exit {result.returncode}')
        documents = PassportDocument.objects.filter(status='ISSUED')
        assert documents.filter(passport_version=latest).count() == 1
        assert documents.filter(passport_version=fixture.version).count() == 1
        assert documents.count() == 2, 'No duplicate issued documents after repeated download'
        print('PASS PostgreSQL: exactly one registered PDF per requested version; all synthetic records discarded.', flush=True)
finally:
    if server:
        server.shutdown()
        server.server_close()
    connections.close_all()
    fixture.doCleanups()
    teardown_databases(db, verbosity=0)
