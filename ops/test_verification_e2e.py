"""Real React/Vite/Django public verification using disposable PostgreSQL only.

No verification response is mocked. Fixture revocation delays the existing outbox
consumer, representing a real worker lag; expired snapshots use an earlier actual
effective_at. No blockchain code, production settings or shared data are changed.
"""
from disposable_tests import DisposableRun, test_database_name
import contextvars
from datetime import timedelta
import json
import os
import secrets
from pathlib import Path
import sys
import threading
from unittest.mock import patch
from uuid import uuid4
from wsgiref.simple_server import make_server, WSGIRequestHandler, WSGIServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'apps.integrations.postgres_test_settings'
os.environ['INTEGRATION_TEST_DB_NAME'] = test_database_name('verification')
import django
django.setup()
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.utils import timezone
from apps.api.test_pdf import PassportPDFAPITests
from apps.credentials.services import revoke_credential
from apps.passports.models import DigitalPassport, PassportDocument
from apps.passports.services import publish_passport_version

settings.ROOT_URLCONF = 'config.urls'
settings.ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
settings.CREDENTIAL_REVOCATION_AUTHORIZER = 'apps.accounts.authorization.authorize_credential_revocation'
settings.PASSPORT_PDF_REQUESTS_PER_MINUTE = 1000


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


class IsolatedServer(WSGIServer):
    allow_reuse_address = False


fixture = PassportPDFAPITests()
server = None
with DisposableRun() as resources:
    resources.database()
    resources.fixture(fixture)
    fixture.setUp()
    # Ephemeral password exists only in this run and is never logged.
    admin_password = secrets.token_urlsafe(32)
    fixture.admin.set_password(admin_password)
    fixture.admin.save(update_fields=['password'])
    historical = fixture.version
    fixture.student.program = 'Synthetic verification acceptance'
    fixture.student.save()
    latest, _ = publish_passport_version(student_id=fixture.student.pk, event_key='PUBLIC-HTTP-LATEST')
    revoked = fixture.issue(fixture.other)
    revoked_passport = DigitalPassport.objects.get(student=fixture.other)
    # Exercise latest=true + revoked without pretending the PDF bytes changed.
    with patch('apps.credentials.passport_refresh.process_passport_refresh_event'):
        revoke_credential(public_reference=revoked.public_reference, actor=fixture.admin, reason='Synthetic public HTTP acceptance')
    now = timezone.now()
    expired_student = fixture.make_student('public-expired')
    # Build the historical award at its actual issuance time, so its earned date
    # cannot follow issuance under the integrated authoritative-date policy.
    with patch('apps.api.test_pdf.timezone.now', return_value=now-timedelta(days=3)):
        expired = fixture.issue(expired_student, issued_at=now-timedelta(days=3), expires_at=now-timedelta(days=1))
    expired_version, _ = publish_passport_version(student_id=expired_student.pk, event_key='PUBLIC-HTTP-EXPIRED-SNAPSHOT', effective_at=now-timedelta(days=2))
    expired_passport = DigitalPassport.objects.get(student=expired_student)

    def case(passport, version):
        return {'passportId': str(passport.pk), 'versionId': str(version.pk), 'passportReference': str(passport.public_reference), 'versionReference': str(version.public_reference)}

    metadata = {
        'testOnly': True, 'admin': {'email': fixture.admin.email, 'password': admin_password},
        'valid': case(fixture.passport, latest), 'historical': case(fixture.passport, historical),
        'revoked': case(revoked_passport, revoked_passport.latest_version), 'expired': case(expired_passport, expired_version),
        'credential': str(fixture.credential.public_reference), 'revokedCredential': str(revoked.public_reference),
        'expiredCredential': str(expired.public_reference), 'unknown': str(uuid4()),
        'privateFields': [fixture.student.email, fixture.student.external_student_id, str(fixture.student.pk)],
    }
    server = make_server('127.0.0.1', 0, get_wsgi_application(), server_class=IsolatedServer, handler_class=QuietHandler)
    context = contextvars.copy_context()
    thread = threading.Thread(target=lambda: context.run(server.serve_forever), daemon=True)
    thread.start()
    resources.server(server, thread)
    env = {**os.environ, 'BTU_TEST_VITE_CACHE': str(Path(settings.MEDIA_ROOT) / 'vite-cache'), 'BTU_DEV_API_TARGET': f'http://127.0.0.1:{server.server_port}', 'BTU_VERIFICATION_FIXTURE': json.dumps(metadata), 'VITE_ENABLE_DEMO': 'false', 'VITE_PUBLIC_VERIFICATION_ENABLED': 'true', 'VITE_PUBLIC_VERIFICATION_SOURCES': 'POSTGRESQL_CREDENTIAL_REGISTRY,POSTGRESQL_PASSPORT_REGISTRY,POSTGRESQL_DOCUMENT_REGISTRY'}
    result = resources.command(['node', 'scripts/check-verification-http.mjs'], cwd=ROOT/'frontend', env=env)
    if result.returncode:
        raise RuntimeError(f'Public verification HTTP acceptance failed with exit {result.returncode}')
    assert PassportDocument.objects.filter(status='ISSUED').count() == 4
    print('PASS PostgreSQL: four real issued PDF registry entries; public uploads issued no additional document.', flush=True)
