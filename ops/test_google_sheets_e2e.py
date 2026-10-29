"""Synthetic Google import -> real HTTP/PostgreSQL/PDF/Anvil acceptance.

Default: provider fixture, never Google. A future live run requires BOTH an
explicit --allow-google-read and an operator-created --live-config, plus manual
source editing by its owner. No Google writes, .env or existing databases.
Run through run_isolated_tests.py to allocate an exclusive PostgreSQL cluster.
"""
import argparse
import contextvars
import copy
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import re
import secrets
import sys
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from wsgiref.simple_server import make_server, WSGIRequestHandler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from config.spreadsheet_sources import credential_path, validate_target

WORKSHEET = 'Passport Skill Records'
HEADERS = ['Institutional Approval', 'Skill ID', 'Student ID', 'Date Earned', 'Record ID', 'Ignored note']
VALID = ['CONFIRMED', 'SYNTHETIC-SKILL', 'SYNTHETIC-STUDENT', '2026-01-01', 'SYNTHETIC-RECORD', 'synthetic']
GRID = [['Synthetic workbook'], [], [], HEADERS, VALID, VALID,
        ['PENDING', *VALID[1:4], 'SYNTHETIC-PENDING', 'synthetic'],
        ['CONFIRMED', VALID[1], '', VALID[3], 'SYNTHETIC-MISSING', 'synthetic'],
        ['CONFIRMED', 'SYNTHETIC-UNAPPROVED', *VALID[2:4], 'SYNTHETIC-BAD-SKILL', 'synthetic'],
        ['CONFIRMED', VALID[1], '=1+1', VALID[3], 'SYNTHETIC-FORMULA', 'synthetic']]


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-config', type=Path)
    parser.add_argument('--allow-google-read', action='store_true')
    args = parser.parse_args(argv)
    if bool(args.live_config) != args.allow_google_read:
        parser.error('Live access needs both --live-config and --allow-google-read after explicit user approval.')
    if not args.live_config:
        return None
    try:
        if args.live_config.stat().st_size > 10_000:
            raise ValueError()
        config = json.loads(args.live_config.read_text(encoding='utf-8-sig'))
        if set(config) != {'target', 'unshared_spreadsheet_id', 'credential_file', 'approval_reference'}:
            raise ValueError()
        if validate_target(config['target']) != 'A1:F20' or config['target']['worksheet'] != WORKSHEET:
            raise ValueError()
        validate_target({**config['target'], 'spreadsheet_id': config['unshared_spreadsheet_id']})
        if config['unshared_spreadsheet_id'] == config['target']['spreadsheet_id']:
            raise ValueError()
        if not isinstance(config['approval_reference'], str) or not 1 <= len(config['approval_reference']) <= 255:
            raise ValueError()
        credential_path(config['credential_file'])
        return config
    except Exception:
        parser.error('Invalid live configuration. Use the synthetic setup in ops/GOOGLE_SHEETS_LIVE.md; no Google request made.')


class Quiet(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def main():
    live = arguments()  # Gate before Django, database creation or credential use.
    from disposable_tests import DisposableRun, test_database_name
    os.environ['DJANGO_SETTINGS_MODULE'] = 'apps.integrations.postgres_test_settings'
    os.environ['INTEGRATION_TEST_DB_NAME'] = test_database_name('google_http')
    import django
    django.setup()
    import requests
    from django.core import mail
    from django.core.management import call_command
    from django.core.wsgi import get_wsgi_application
    from django.db import connections
    from django.test import TransactionTestCase, override_settings
    from apps.accounts.models import User
    from apps.blockchain.chain import artifact
    from apps.blockchain.models import PassportAnchor
    from apps.blockchain.tests import ChainDataMixin
    from apps.credentials.models import Credential
    from apps.integrations.importers.mapping import bounded_grid
    from apps.integrations.importers.profiles import provision_profile
    from apps.integrations.importers.sheet_source import read_profile_sheet
    from apps.integrations.models import SpreadsheetAward
    from apps.integrations.test_spreadsheet_mapping import definition
    from apps.passports.models import DigitalPassport
    from apps.skills.models import Skill, VerifiedAchievement
    from apps.students.models import Student
    from web3 import Web3

    class Fixture(ChainDataMixin, TransactionTestCase):
        pass

    provider = 'REAL_GOOGLE_API' if live else 'SYNTHETIC_PROVIDER_FIXTURE'
    print(f'Google source: {provider}. All database and chain resources are disposable.', flush=True)
    with DisposableRun() as owned:
        owned.database()
        Fixture.setUpClass()
        owned.callback(Fixture.doClassCleanups)
        fixture = Fixture()
        owned.fixture(fixture)
        fixture.setUp()
        owned.callback(fixture.tearDown)
        target = live['target'] if live else {'spreadsheet_id': 'SYNTHETIC_SHEET_ID', 'worksheet': WORKSHEET, 'range': 'A1:F20'}
        denied = live['unshared_spreadsheet_id'] if live else 'SYNTHETIC_UNSHARED_ID'
        path = live['credential_file'] if live else str(Path(fixture.key_dir.name) / 'synthetic-google.json')
        if not live:
            Path(path).write_text('{}')
        owned.enter_context(override_settings(ALLOWED_HOSTS=['127.0.0.1'],
            BTU_CLASSROOM_ISSUER_REFERENCE='BTU-UNIVERSITY', BTU_AUTHORIZED_COMPLETION_SOURCES=['BTU_GOOGLE_SHEETS'],
            BTU_SPREADSHEET_GOOGLE_SOURCES={'approved': target, 'denied': {**target, 'spreadsheet_id': denied}},
            GOOGLE_SERVICE_ACCOUNT_FILE=path, PASSPORT_BLOCKCHAIN_CONFIRMATIONS=3))
        current_grid = copy.deepcopy(GRID)
        if not live:
            def factory(**kwargs):
                assert kwargs['scopes'] == ['https://www.googleapis.com/auth/spreadsheets.readonly']
                client = MagicMock()
                def open_by_key(key):
                    if key == denied:
                        raise PermissionError('PRIVATE_PROVIDER_DETAIL')
                    assert key == target['spreadsheet_id']
                    book = MagicMock()
                    def worksheet(name):
                        assert name == WORKSHEET
                        tab = MagicMock()
                        def get(area, **options):
                            assert area == 'A1:F20' and options == {'value_render_option': 'FORMULA'}
                            return copy.deepcopy(current_grid)
                        tab.get.side_effect = get
                        return tab
                    book.worksheet.side_effect = worksheet
                    return book
                client.open_by_key.side_effect = open_by_key
                return client
            owned.enter_context(patch('gspread.service_account', side_effect=factory))

        # Reject any source other than the exact fictional template before issuing.
        probe = SimpleNamespace(definition={'google_source': 'approved', 'worksheet': WORKSHEET})
        rows, _ = read_profile_sheet(probe)
        assert rows == bounded_grid(copy.deepcopy(GRID)), 'Source must match the synthetic template exactly.'
        student = Student.objects.create(external_student_id=VALID[2], first_name='Synthetic', last_name='Google Student',
            email='synthetic.google@btu.edu.ge', program='AI', education_level='Bachelor', student_status='ACTIVE')
        Skill.objects.create(skill_code=VALID[1], skill_name='Synthetic Google skill', category='AI',
            description='Synthetic acceptance only', stamp_type='FOCUSED', badge_asset_id='synthetic')
        password = secrets.token_urlsafe(32)
        admin = User.objects.create_admin_user(email='synthetic.google.admin@btu.edu.ge', password=password,
                                              permission_codenames=['import_completions'])
        data = definition()
        data['google_source'] = 'approved'
        profile = provision_profile({'key': 'synthetic-google', 'version': 1, 'source': 'BTU_GOOGLE_SHEETS',
            'kind': 'SKILL_AWARD', 'definition': data,
            'approval_reference': live['approval_reference'] if live else 'SYNTHETIC-LOCAL-APPROVAL'})
        profile.enabled = True
        profile.save(update_fields=['enabled'])
        bad = provision_profile({'key': 'synthetic-denied', 'version': 1, 'source': profile.source, 'kind': profile.kind,
            'definition': {**data, 'google_source': 'denied'}, 'approval_reference': profile.approval_reference})
        bad.enabled = True
        bad.save(update_fields=['enabled'])
        unknown = provision_profile({'key': 'synthetic-unconfigured', 'version': 1, 'source': profile.source, 'kind': profile.kind,
            'definition': {**data, 'google_source': 'unconfigured'}, 'approval_reference': profile.approval_reference})
        unknown.enabled = True
        unknown.save(update_fields=['enabled'])

        def serve():
            try:
                server.serve_forever()
            finally:
                connections.close_all()
        server = make_server('127.0.0.1', 0, get_wsgi_application(), handler_class=Quiet)
        context = contextvars.copy_context()
        thread = threading.Thread(target=lambda: context.run(serve), daemon=True)
        thread.start()
        owned.server(server, thread)
        client, learner, public = [requests.Session() for _ in range(3)]
        for session in (client, learner, public):
            session.trust_env = False
            owned.callback(session.close)
        base = f'http://127.0.0.1:{server.server_port}'
        count = 0

        def request(session, method, url, status=200, csrf=True, **kwargs):
            nonlocal count
            headers = {'X-CSRFToken': session.cookies.get('csrftoken', '')} if csrf and method != 'GET' else {}
            response = session.request(method, base + url, headers=headers, timeout=90, **kwargs)
            count += 1
            assert response.status_code == status, f'Unexpected HTTP status at {url}: {response.status_code}'
            if '/api/integrations/import/' in url:
                assert 'no-store' in response.headers.get('Cache-Control', '')
            return response

        def preview(which=profile, status=201, csrf=True, **extra):
            return request(client, 'POST', '/api/integrations/import/google-sheets/preview/', status=status, csrf=csrf,
                           json={'profile_id': str(which.pk), **extra}).json()

        def confirm(snapshot, status=200, **changes):
            return request(client, 'POST', f"/api/integrations/import/previews/{snapshot['id']}/confirm/", status=status,
                json={'confirm': True, 'snapshot_sha256': snapshot['snapshot_sha256'], **changes}).json()

        def counts():
            return (Credential.objects.filter(student=student).count(), VerifiedAchievement.objects.filter(student=student).count(),
                    DigitalPassport.objects.filter(student=student).count(), SpreadsheetAward.objects.filter(actor=admin).count())

        request(client, 'GET', '/api/integrations/import/profiles/', status=403)
        request(client, 'GET', '/api/accounts/csrf/')
        request(client, 'POST', '/api/accounts/login/', json={'email': admin.email, 'password': password})
        preview(csrf=False, status=403)
        preview(status=400, spreadsheet_id=target['spreadsheet_id'])
        assert preview(which=unknown, status=503)['code'] == 'GOOGLE_SOURCE_UNAVAILABLE'
        unavailable = preview(which=bad, status=503)
        assert unavailable['code'] == 'GOOGLE_SOURCE_UNAVAILABLE' and denied not in str(unavailable)
        first = preview()
        report = first['report']
        assert report['header_row'] == 4
        assert (report['valid_records'], report['duplicate_records'], report['review_records'], report['invalid_records']) == (1, 1, 1, 3)
        assert counts() == (0, 0, 0, 0)
        request(learner, 'GET', f"/api/integrations/import/previews/{first['id']}/", status=403)
        assert confirm(first, status=409, snapshot_sha256='0' * 64)['code'] == 'PREVIEW_DIGEST_MISMATCH'
        assert counts() == (0, 0, 0, 0)
        if live:
            input('In the synthetic Sheet only, change F5 from synthetic to synthetic changed. Then press Enter: ')
        else:
            current_grid[4][5] = 'synthetic changed'
        expected = copy.deepcopy(GRID)
        expected[4][5] = 'synthetic changed'
        rows, _ = read_profile_sheet(probe)
        assert rows == bounded_grid(expected), 'Only the documented synthetic cell change is allowed.'
        assert confirm(first, status=409)['code'] == 'SOURCE_CHANGED_REVIEW_REQUIRED'
        assert counts() == (0, 0, 0, 0)
        reviewed = preview()
        assert reviewed['snapshot_sha256'] != first['snapshot_sha256']
        assert confirm(reviewed)['result']['issued'] == 1
        assert counts() == (1, 1, 1, 1)
        confirm(reviewed)
        assert counts() == (1, 1, 1, 1)
        repeated = preview()
        assert repeated['report']['valid_records'] == 0
        assert counts() == (1, 1, 1, 1)
        print('PASS Google import HTTP: permissions, private review, mappings, source/digest guards, confirmation and replay.', flush=True)

        call_command('run_backend_workers', once=True, stdout=StringIO())
        for _ in range(10):
            call_command('process_blockchain_proofs', stdout=StringIO())
            pending = PassportAnchor.objects.exclude(state__in=['CONFIRMED', 'FAILED'])
            if not pending.exists():
                break
            fixture.local.mine_blocks(1)
            pending.update(next_attempt_at=None)
        assert not PassportAnchor.objects.exclude(state='CONFIRMED').exists()
        request(learner, 'GET', '/api/accounts/csrf/')
        request(learner, 'POST', '/api/accounts/otp/request/', status=202, json={'email': student.email})
        code = re.search(r'code is: ([0-9]{6})', mail.outbox[-1].body).group(1)
        request(learner, 'POST', '/api/accounts/otp/verify/', json={'email': student.email, 'code': code})
        request(learner, 'GET', f"/api/integrations/import/previews/{reviewed['id']}/", status=403)
        assert request(learner, 'GET', '/api/student/achievements/').json()['count'] == 1
        assert request(learner, 'GET', '/api/student/passport/').json()['status'] == 'BLOCKCHAIN_VERIFIED'
        pdf = request(learner, 'GET', '/api/student/passport/pdf/download/').content
        assert pdf.startswith(b'%PDF-')
        passport = DigitalPassport.objects.get(student=student)
        verified = request(public, 'GET', f'/api/verification/passport/{passport.public_reference}/').json()
        assert verified['status'] == 'VALID'
        proof = verified['blockchain']
        assert proof['blockchain_verified'] and proof['confirmations'] >= 3 and proof['environment'] == 'LOCAL_ANVIL'
        observer = Web3(Web3.HTTPProvider(fixture.local.rpc_url, request_kwargs={'timeout': 5}, exception_retry_configuration=None))
        registry = observer.eth.contract(address=Web3.to_checksum_address(proof['contract_address']), abi=artifact()['abi'])
        assert observer.eth.chain_id == 31337
        receipt = observer.eth.get_transaction_receipt(proof['transaction_hash'])
        assert receipt['status'] == 1 and observer.eth.get_block(receipt['blockNumber'])['hash'] == receipt['blockHash']
        assert observer.eth.block_number - receipt['blockNumber'] + 1 >= 3
        key = lambda name: bytes.fromhex(proof[name])
        assert list(registry.functions.commitments(key('document_key')).call()) == [
            key('passport_key'), key('version_key'), key('commitment'), Web3.to_checksum_address(proof['issuer_address'])]
        assert registry.functions.passportState(key('passport_key')).call() == 1
        assert hashlib.sha256(pdf).hexdigest() == proof['pdf_sha256']
        result = request(public, 'POST', '/api/verification/document/',
                         files={'file': ('synthetic.pdf', pdf, 'application/pdf')}).json()
        assert result['status'] == 'VALID' and result['authentic'] is True
        tampered = request(public, 'POST', '/api/verification/document/',
                           files={'file': ('modified.pdf', pdf + b'\n%modified', 'application/pdf')}).json()
        assert tampered['authentic'] is False and tampered['status'] != 'VALID'
        connections.close_all()
        print(f'PASS {provider}: {count} real local HTTP requests; PostgreSQL achievement, Passport, PDF, independently checked Anvil and tamper rejection.', flush=True)
        if not live:
            print('REAL_GOOGLE_API: NOT RUN. No external authentication or live acceptance claimed.', flush=True)


if __name__ == '__main__':
    main()
