"""One assembled synthetic automation -> immutable PDF -> real Anvil HTTP flow.

Set PASSPORT_ACCEPTANCE_ROOT to the coordinator's assembled candidate. No live
Google service, persistent database, browser mocks, or public chain is used.
Launch from an owned PostgreSQL wrapper with a short, unique TEMP directory.
"""
import contextvars
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import secrets
import sys
import threading
from unittest.mock import patch
from wsgiref.simple_server import make_server, WSGIRequestHandler

HERE = Path(os.environ['BTU_TEST_ARTIFACTS']).resolve()
HERE.mkdir(parents=True, exist_ok=True)
ROOT = Path(os.environ.get('PASSPORT_ACCEPTANCE_ROOT', Path(__file__).resolve().parents[1])).resolve()
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'ops')]
from disposable_tests import DisposableRun, test_database_name
os.environ['DJANGO_SETTINGS_MODULE'] = 'apps.integrations.postgres_test_settings'
os.environ['INTEGRATION_TEST_DB_NAME'] = test_database_name('auto_pdf_chain')
import django
django.setup()
import pymupdf
import requests
from django.core.management import call_command
from django.core.wsgi import get_wsgi_application
from django.db import connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from apps.accounts.models import User
from apps.blockchain.chain import artifact
from apps.blockchain.models import PassportAnchor
from apps.blockchain.tests import ChainDataMixin
from apps.integrations.importers.mapping import digest
from apps.integrations.importers.profiles import provision_profile
from apps.integrations.models import SpreadsheetAutomation, SpreadsheetPoll
from apps.integrations.spreadsheet_automation import poll_due_sources
from apps.integrations.test_spreadsheet_mapping import definition, grid
from apps.passports.document_services import generate_passport_document
from apps.passports.models import PassportDocument
from apps.skills.models import Skill
from web3 import Web3


class Fixture(ChainDataMixin, TransactionTestCase):
    pass


class Quiet(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def main():
    evidence = {'synthetic': True, 'google': 'synthetic read-only provider', 'chain': 'LOCAL_ANVIL', 'checks': []}
    with DisposableRun() as owned:
        owned.database()
        Fixture.setUpClass()
        owned.callback(Fixture.doClassCleanups)
        fixture = Fixture()
        owned.fixture(fixture)
        fixture.setUp()
        owned.callback(fixture.tearDown)
        assert fixture.process() == 'CONFIRMED'
        fixture.anchor.refresh_from_db()
        original_pdf, original_hash = fixture.pdf_bytes(), fixture.document.pdf_sha256
        original_snapshot = fixture.version.content_sha256
        original_proof = (fixture.anchor.pk, fixture.anchor.transaction_hash, fixture.anchor.commitment)
        passport = fixture.version.passport
        identity, first_issue = passport.pk, passport.first_issued_at
        fixture.student.student_status = 'ACTIVE'
        fixture.student.save(update_fields=['student_status'])
        extra = Skill.objects.create(skill_code='SYNTHETIC-AUTO-CHAIN', skill_name='Automatic AI Evidence',
            category='AI', description='Synthetic authoritative learning evidence.', stamp_type='FOCUSED', badge_asset_id='synthetic')
        password = secrets.token_urlsafe(24)
        actor = User.objects.create_admin_user(email='auto-chain.synthetic@btu.edu.ge', password=password,
            permission_codenames=['import_completions', 'view_student_records', 'manage_credentials'])
        target = {'spreadsheet_id': 'SYNTHETIC_SHEET_ID', 'worksheet': 'Passport Skill Records', 'range': 'A1:F20'}
        owned.enter_context(override_settings(ALLOWED_HOSTS=['127.0.0.1'],
            BTU_CLASSROOM_ISSUER_REFERENCE='BTU-UNIVERSITY', BTU_AUTHORIZED_COMPLETION_SOURCES=['BTU_GOOGLE_SHEETS'],
            BTU_SPREADSHEET_GOOGLE_SOURCES={'approved': target}, PASSPORT_PDF_REQUESTS_PER_MINUTE=1000))
        d = definition()
        d.update(google_source='approved', allowed_skill_codes=[extra.skill_code])
        profile = provision_profile({'key': 'synthetic-auto-chain', 'version': 1, 'source': 'BTU_GOOGLE_SHEETS',
            'kind': 'SKILL_AWARD', 'approval_reference': 'SYNTHETIC-INSTITUTIONAL-POLICY', 'definition': d})
        profile.enabled = True
        profile.save(update_fields=['enabled'])
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
        base = f'http://127.0.0.1:{server.server_port}'
        private, public = requests.Session(), requests.Session()
        owned.callback(private.close)
        owned.callback(public.close)
        def request(session, method, path, **kwargs):
            headers = {'X-CSRFToken': session.cookies.get('csrftoken', '')}
            response = session.request(method, base + path, headers=headers, timeout=30, **kwargs)
            assert response.status_code == 200, (path, response.status_code, response.text[:150])
            return response
        request(private, 'GET', '/api/accounts/csrf/')
        request(private, 'POST', '/api/accounts/login/', json={'email': actor.email, 'password': password})
        old_path = f'/api/admin/passports/{passport.pk}/pdf/download/?version_id={fixture.version.pk}'
        assert request(private, 'GET', old_path).content == original_pdf
        with patch('apps.passports.document_services.renderer_fingerprint', side_effect=AssertionError('Immutable version consulted renderer')):
            assert generate_passport_document(passport_version_id=fixture.version.pk, storage=fixture.storage).pk == fixture.document.pk
        request(private, 'POST', f'/api/integrations/import/automatic-sources/{profile.pk}/', json={
            'enabled': True, 'confirm': True, 'interval_seconds': 60, 'authorization_reference': 'SYNTHETIC-CONTINUING-AUTHORITY'})
        rows = grid([fixture.student.external_student_id, 'SYNTHETIC-AUTO-RECORD', extra.skill_code, '2026-10-18', 'CONFIRMED'])
        def read(profile):
            return rows, digest({'target': target, 'rows': rows})
        owned.enter_context(patch('apps.integrations.spreadsheet_automation.read_profile_sheet', side_effect=read))
        owned.enter_context(patch('apps.integrations.importers.preview.read_profile_sheet', side_effect=read))
        poll_due_sources(limit=1)
        assert SpreadsheetPoll.objects.get().state == 'COMPLETED'
        call_command('run_backend_workers', once=True, stdout=StringIO())
        for _ in range(8):
            call_command('process_blockchain_proofs', stdout=StringIO())
            pending = PassportAnchor.objects.exclude(state__in=['CONFIRMED', 'FAILED'])
            if not pending.exists():
                break
            fixture.local.mine_blocks(1)
            pending.update(next_attempt_at=None)
        assert not PassportAnchor.objects.exclude(state='CONFIRMED').exists()
        passport.refresh_from_db()
        assert (passport.pk, passport.first_issued_at) == (identity, first_issue)
        assert passport.latest_version_id != fixture.version.pk
        document = PassportDocument.objects.get(passport_version=passport.latest_version, status='ISSUED')
        current_path = f'/api/admin/passports/{passport.pk}/pdf/download/'
        current_pdf = request(private, 'GET', current_path).content
        assert hashlib.sha256(current_pdf).hexdigest() == document.pdf_sha256
        with pymupdf.open(stream=current_pdf, filetype='pdf') as pdf:
            text = ' '.join(' '.join(page.get_text() for page in pdf).split())
            assert 'VERIFY DOCUMENT' in text and '2026-10-18' in text
        proof = request(public, 'GET', f'/api/verification/blockchain/document/{document.public_reference}/').json()
        assert proof['blockchain_verified'] is True and proof['status'] == 'CONFIRMED'
        observer = Web3(Web3.HTTPProvider(fixture.local.rpc_url, request_kwargs={'timeout': 5}, exception_retry_configuration=None))
        assert observer.eth.chain_id == 31337
        registry = observer.eth.contract(address=fixture.gateway.contract.address, abi=artifact()['abi'])
        receipt = observer.eth.get_transaction_receipt(proof['transaction_hash'])
        assert receipt['status'] == 1
        commitment = registry.functions.commitments(bytes.fromhex(proof['document_key'])).call()
        assert bytes(commitment[2]).hex() == proof['commitment']
        original_result = request(public, 'POST', '/api/verification/document/', files={'file': ('original.pdf', current_pdf, 'application/pdf')}).json()
        altered = request(public, 'POST', '/api/verification/document/', files={'file': ('altered.pdf', current_pdf + b'\n%changed', 'application/pdf')}).json()
        assert original_result['authentic'] is True and altered['authentic'] is False
        assert original_result['status'] == 'VALID' and altered['status'] != 'VALID'
        old_result = request(public, 'POST', '/api/verification/document/', files={'file': ('old.pdf', original_pdf, 'application/pdf')}).json()
        assert old_result['authentic'] is True and old_result['is_latest'] is False
        assert request(private, 'GET', old_path).content == original_pdf
        fixture.document.refresh_from_db()
        fixture.version.refresh_from_db()
        fixture.anchor.refresh_from_db()
        assert (fixture.document.pdf_sha256, fixture.version.content_sha256) == (original_hash, original_snapshot)
        assert (fixture.anchor.pk, fixture.anchor.transaction_hash, fixture.anchor.commitment) == original_proof
        request(private, 'POST', f'/api/integrations/import/automatic-sources/{profile.pk}/', json={'enabled': False})
        assert SpreadsheetAutomation.objects.get().enabled is False
        evidence.update(old_pdf_sha256=original_hash, new_pdf_sha256=document.pdf_sha256,
            old_snapshot_sha256=original_snapshot, new_snapshot_sha256=passport.latest_version.content_sha256,
            new_transaction=proof['transaction_hash'], checks=['HTTP administrator enable', 'automatic confirmed award',
                'same Passport ID and first issue', 'new frozen earned date', 'new neutral PDF final bytes hashed',
                'independent successful Anvil receipt and commitment', 'HTTP original accepted', 'HTTP altered rejected',
                'HTTP current and historical private downloads', 'old snapshot PDF hash and proof unchanged', 'HTTP disable'])
        (HERE / 'automation-current.pdf').write_bytes(current_pdf)
        connections.close_all()
    evidence['owned_cleanup'] = 'PASS'
    (HERE / 'AUTOMATION_PDF_CHAIN_RESULTS.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print('PASS_AUTOMATION_PDF_CHAIN ' + json.dumps(evidence), flush=True)


if __name__ == '__main__':
    main()
