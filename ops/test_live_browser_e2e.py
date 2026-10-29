"""Owned Chrome -> Vite -> Django -> PostgreSQL/Anvil acceptance.

Use ops/run_isolated_tests.py --browser-http. No production settings or public
chain; private fixture mail/password files are destroyed on every exit.
"""
import contextvars
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from wsgiref.simple_server import make_server, WSGIRequestHandler

from disposable_tests import DisposableRun, test_database_name

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'apps.integrations.postgres_test_settings'
os.environ['INTEGRATION_TEST_DB_NAME'] = test_database_name('live_browser')
import django
django.setup()
import requests
from django.conf import settings
from django.core.mail.backends.locmem import EmailBackend
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application
from django.db import connections
from django.test import TransactionTestCase, override_settings
from apps.accounts.models import User
from apps.blockchain.models import PassportAnchor
from apps.blockchain.services import process_batch, document_proof
from apps.blockchain.tests import ChainDataMixin
from apps.passports.models import PassportDocument
from apps.passports.publication import process_publications
from apps.passports.services import publish_passport_version


class Fixture(ChainDataMixin, TransactionTestCase):
    pass


class Quiet(WSGIRequestHandler):
    def log_message(self, *args):
        pass


# Set only inside the owned run; never exposed through an HTTP control endpoint.
mailbox_path = None


class TestMailbox(EmailBackend):
    def send_messages(self, messages):
        result = super().send_messages(messages)
        for message in messages:
            code = re.search(r'code is: ([0-9]{6})', message.body)
            if code:
                private = json.loads(mailbox_path.read_text())
                if private['studentEmail'] in message.to:
                    private['otp'] = code.group(1)
                    mailbox_path.write_text(json.dumps(private), encoding='utf-8')
        return result


def main():
    global mailbox_path
    google_browser = '--google-auth-browser' in sys.argv
    google_review = '--google-auth-review' in sys.argv
    manual = '--manual-demo' in sys.argv or '--demo-smoke' in sys.argv
    if not manual and not os.environ.get('BTU_BROWSER_TOOLS'):
        raise RuntimeError('Set BTU_BROWSER_TOOLS to isolated Playwright tools.')
    output = None if manual else Path(tempfile.mkdtemp(prefix='btu-live-browser-results-'))
    with DisposableRun() as owned:
        if manual:
            print('Preparing owned demo database and migrations...', flush=True)
        owned.database()
        if manual:
            print('Starting fresh local Anvil and preparing synthetic records...', flush=True)
        Fixture.setUpClass()
        owned.callback(Fixture.doClassCleanups)
        fixture = Fixture()
        owned.fixture(fixture)
        fixture.setUp()
        owned.callback(fixture.tearDown)
        artifact_dir = Path(owned.enter_context(tempfile.TemporaryDirectory(prefix='btu-live-browser-private-')))
        mailbox_path = artifact_dir / 'preview-private.json'
        owned.enter_context(override_settings(
            ROOT_URLCONF='config.urls', ALLOWED_HOSTS=['127.0.0.1'],
            PASSPORT_BLOCKCHAIN_CONFIRMATIONS=3,
            EMAIL_BACKEND='__main__.TestMailbox',
            **({'PASSWORD_HASHERS': ['django.contrib.auth.hashers.PBKDF2PasswordHasher']} if manual else {}),
        ))
        fixture.student.email = 'browser.student@btu.edu.ge'
        fixture.student.save(update_fields=['email'])
        fixture.skill.skill_name = 'Synthetic AI Reasoning'
        fixture.skill.save(update_fields=['skill_name'])
        User.objects.create_user(email=fixture.student.email, student=fixture.student, is_email_verified=True)
        password = secrets.token_urlsafe(32)
        admin = User.objects.create_admin_user(
            email='browser.admin@btu.edu.ge', password=password,
            permission_codenames={'view_student_records', 'manage_credentials', 'revoke_credentials',
                                  'manage_student_accounts', 'import_completions', 'sync_classroom',
                                  'manage_passport_lifecycle'} |
                                 ({'manage_legal_identity'} if manual else set()),
        )
        if manual:
            # Consume the fixture credential's real durable refresh before
            # publishing so startup has no hidden pending version update.
            call_command('process_passport_refreshes', batch_size=20)
        version, _ = publish_passport_version(student_id=fixture.student.pk, event_key='SYNTHETIC-BROWSER-V2')
        process_publications(20)
        for _ in range(8):
            process_batch()
            pending = PassportAnchor.objects.exclude(state__in=['CONFIRMED', 'FAILED'])
            if not pending.exists():
                break
            fixture.local.mine_blocks(1)
            pending.update(next_attempt_at=None)
        assert not PassportAnchor.objects.exclude(state='CONFIRMED').exists()
        document = PassportDocument.objects.get(passport_version=version, status='ISSUED')
        assert document_proof(document.public_reference)['blockchain_verified'] is True
        if manual:
            print('Synthetic PDF proofs confirmed; starting Django/Vite...', flush=True)
        mailbox_path.write_text(json.dumps({
            'studentEmail': fixture.student.email, 'adminEmail': admin.email,
            'adminPassword': password, 'otp': None,
        }), encoding='utf-8')
        mailbox_path.chmod(0o600)
        google_client = None
        if google_browser or google_review:
            from google_auth_review import configure
            google_client = configure(owned, artifact_dir, ROOT, synthetic=google_browser)
        review_stop = None
        synthetic_source = None
        if '--review-stop-file' in sys.argv:
            review_stop = Path(sys.argv[sys.argv.index('--review-stop-file') + 1]).resolve()
            if not google_review:
                from review_session import prepare_synthetic_source
                synthetic_source = prepare_synthetic_source(owned, fixture, artifact_dir)
            else:
                synthetic_source = {'google_auth_configured': bool(google_client), 'google_provider': 'LIVE_NOT_TESTED'}
        (artifact_dir / 'preview-runtime.json').write_text(json.dumps({
            'synthetic': True, 'studentId': str(fixture.student.pk),
            'credentialId': str(fixture.credential.pk),
            'credentialReference': str(fixture.credential.public_reference),
            'passportReference': str(version.passport.public_reference),
            'historicalVersionId': str(fixture.version.pk),
            'historicalVersionReference': str(fixture.version.public_reference),
            'pdfPath': fixture.storage.path(document.storage_key),
        }), encoding='utf-8')
        server = make_server('127.0.0.1', 0, get_wsgi_application(), handler_class=Quiet)
        context = contextvars.copy_context()
        def serve():
            try:
                server.serve_forever()
            finally:
                connections.close_all()
        thread = threading.Thread(target=lambda: context.run(serve), daemon=True)
        thread.start()
        owned.server(server, thread)
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', int(os.environ.get('BTU_GOOGLE_AUTH_PORT', '5188')) if google_review else 0))
            port = probe.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        env = {**os.environ, 'VITE_ENABLE_DEMO': 'false',
               'BTU_DEV_API_TARGET': f'http://127.0.0.1:{server.server_port}',
               'BTU_LIVE_TEST_URL': base, 'BTU_LIVE_TEST_ARTIFACTS': str(artifact_dir),
               'BTU_TEST_VITE_CACHE': str(artifact_dir / 'vite-cache'), 'BTU_TEST_VITE_PORT': str(port)}
        if google_client is not None:
            env['VITE_GOOGLE_CLIENT_ID'] = google_client
        code = "import {createServer} from 'vite'; const s=await createServer({cacheDir:process.env.BTU_TEST_VITE_CACHE,server:{host:'127.0.0.1',port:Number(process.env.BTU_TEST_VITE_PORT),strictPort:true}}); await s.listen();"
        log = owned.enter_context((artifact_dir / 'vite.log').open('w'))
        flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {'start_new_session': True}
        vite = subprocess.Popen(['node', '--input-type=module', '-e', code], cwd=ROOT / 'frontend',
                                env=env, stdout=log, stderr=log, **flags)
        def stop_vite():
            if vite.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(vite.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    os.killpg(vite.pid, signal.SIGTERM)
                try:
                    vite.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    vite.kill(); vite.wait()
        owned.callback(stop_vite)
        client = requests.Session()
        client.trust_env = False
        owned.callback(client.close)
        for _ in range(60):
            if vite.poll() is not None:
                raise RuntimeError('Owned Vite server stopped during startup.')
            try:
                if client.get(base + '/api/accounts/csrf/', timeout=2).status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(.25)
        else:
            raise RuntimeError('Owned Vite/Django proxy did not become ready.')
        if manual:
            from manual_demo import recording_session
            if review_stop:
                ready = {'synthetic': True, 'mode': 'LIVE', 'frontend': base,
                         'backend': f'http://127.0.0.1:{server.server_port}',
                         'anvil': fixture.local.rpc_url, 'postgres_port': settings.DATABASES['default']['PORT'],
                         'private_fixture': str(mailbox_path), 'stop_file': str(review_stop),
                         'pid': os.getpid(), **synthetic_source}
                (review_stop.parent / 'review-ready.json').write_text(json.dumps(ready, indent=2), encoding='utf-8')
            recording_session(owned, fixture, base, mailbox_path, smoke='--demo-smoke' in sys.argv,
                              stop_file=review_stop)
            connections.close_all()
            return
        try:
            script = 'scripts/check-google-auth-browser.mjs' if google_browser else 'scripts/check-passport-browser.mjs'
            result = owned.command(['node', script], cwd=ROOT / 'frontend', env=env)
            if result.returncode:
                raise RuntimeError('Real Chrome integration failed; inspect sanitized test artifacts.')
        finally:
            # Strict allowlist: never retain private credentials/OTPs, PDFs,
            # database/media files or provider configuration in review artifacts.
            for path in artifact_dir.iterdir():
                if path.suffix == '.png' or path.name in {'browser-acceptance-results.json', 'browser-acceptance-failure.json', 'google-auth-browser-results.json', 'google-auth-browser-failure.json'}:
                    shutil.copy2(path, output / path.name)
            print('Synthetic browser review artifacts:', output, flush=True)
        result_name = 'google-auth-browser-results.json' if google_browser else 'browser-acceptance-results.json'
        assert json.loads((output / result_name).read_text())['mockedResponses'] is False
        connections.close_all()
    print('PASS cleanup: browser fixtures, private mailbox, server, Vite, signer and database removed.', flush=True)


if __name__ == '__main__':
    main()
