"""Real loopback HTTP acceptance with owned PostgreSQL, media, mail and Anvil.

Run through ops/run_isolated_tests.py --full. No .env, public RPC, real student
data, persistent databases or frontend implementation is used or changed.
"""
import contextvars
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import re
import secrets
import socket
import sys
import threading
import time
import traceback
from unittest.mock import patch
from uuid import uuid4
from wsgiref.simple_server import make_server, WSGIRequestHandler

from disposable_tests import DisposableRun, test_database_name

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'apps.integrations.postgres_test_settings'
os.environ['INTEGRATION_TEST_DB_NAME'] = test_database_name('chain_http')

import django
django.setup()
import requests
from openpyxl import Workbook
from django.conf import settings
from django.core import mail
from django.core.management import call_command
from django.core.signals import got_request_exception
from django.core.wsgi import get_wsgi_application
from django.db import connections
from django.test import TransactionTestCase, override_settings
from apps.accounts.models import User
from apps.blockchain.models import PassportAnchor
from apps.blockchain.rpc import BoundedHTTPProvider
from apps.blockchain.tests import ChainDataMixin
from apps.credentials.models import Credential
from apps.integrations.importers.validators import REQUIRED_FIELDS
from apps.passports.models import DigitalPassport, PassportDocument
from apps.passports.services import get_or_create_passport
from apps.skills.models import Skill
from apps.students.models import Student


class Fixture(ChainDataMixin, TransactionTestCase):
    pass


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def main():
    evidence = {'environment': 'LOCAL_ANVIL', 'synthetic_data': True, 'http_requests': 0,
                'journeys': {}, 'responses': []}
    with DisposableRun() as resources:
        resources.database()
        Fixture.setUpClass()
        resources.callback(Fixture.doClassCleanups)
        fixture = Fixture()
        resources.fixture(fixture)
        fixture.setUp()
        resources.callback(fixture.tearDown)
        resources.enter_context(override_settings(
            ALLOWED_HOSTS=['127.0.0.1'],
            BTU_CLASSROOM_ISSUER_REFERENCE='BTU-UNIVERSITY',
            BTU_AUTHORIZED_COMPLETION_SOURCES=['BTU_EXCEL'],
            CREDENTIAL_REVOCATION_AUTHORIZER='apps.accounts.authorization.authorize_credential_revocation',
        ))
        student = Student.objects.create(
            external_student_id='HTTP-SYNTHETIC-001', first_name='Synthetic',
            last_name='Student', email='http.student@btu.edu.ge', program='AI',
            education_level='Bachelor', student_status='Active',
        )
        password = secrets.token_urlsafe(32)
        admin = User.objects.create_admin_user(
            email='http.registrar@btu.edu.ge', password=password,
            permission_codenames={'view_student_records', 'import_completions',
                'revoke_credentials', 'manage_legal_identity', 'manage_passport_lifecycle'},
        )
        limited = User.objects.create_admin_user(
            email='http.reader@btu.edu.ge', password=password,
            permission_codenames={'view_student_records'},
        )
        for code in ('AI_LITERACY', 'AI_FUNDAMENTALS', 'MACHINE_LEARNING', 'DATA_ANALYSIS'):
            Skill.objects.create(skill_code=code, skill_name=code.replace('_', ' ').title(),
                category='AI', description='Synthetic assessed AI learning evidence.',
                stamp_type='FOCUSED', badge_asset_id='synthetic')

        server_errors = []
        def capture_server_error(sender, **kwargs):
            error = sys.exception()
            if error is not None:
                # Test-only stack locations, without request bodies, exception
                # messages, local variables or credential/provider values.
                server_errors.append((type(error).__name__, [
                    (Path(frame.filename).name, frame.name, frame.lineno)
                    for frame in traceback.extract_tb(error.__traceback__)
                ]))
        got_request_exception.connect(capture_server_error, weak=False)
        resources.callback(got_request_exception.disconnect, capture_server_error)
        server = make_server('127.0.0.1', 0, get_wsgi_application(), handler_class=QuietHandler)
        context = contextvars.copy_context()
        def serve():
            try:
                server.serve_forever()
            finally:
                # Django connections belong to this thread. Main-thread cleanup
                # cannot close one left open by an interrupted/failed request.
                connections.close_all()
        thread = threading.Thread(target=lambda: context.run(serve), daemon=True)
        thread.start()
        resources.server(server, thread)
        base = f'http://127.0.0.1:{server.server_port}'
        public, learner, registrar, reader = [requests.Session() for _ in range(4)]
        for session in (public, learner, registrar, reader):
            session.trust_env = False
            resources.callback(session.close)

        rpc_calls = [0]
        original_transport = BoundedHTTPProvider._make_request
        def count_transport(provider, method, data):
            rpc_calls[0] += 1
            return original_transport(provider, method, data)
        resources.enter_context(patch.object(BoundedHTTPProvider, '_make_request', count_transport))

        def request(session, method, path, expected=200, *, capture=False, csrf=True, **kwargs):
            headers = {}
            if method != 'GET' and csrf:
                headers['X-CSRFToken'] = session.cookies.get('csrftoken', '')
            before = rpc_calls[0]
            start = time.monotonic()
            response = session.request(method, base + path, headers=headers, timeout=15, **kwargs)
            evidence['http_requests'] += 1
            elapsed = round(time.monotonic() - start, 4)
            assert response.status_code == expected, (
                method, path, response.status_code, expected,
                server_errors[-1] if response.status_code >= 500 and server_errors else None,
            )
            if capture:
                evidence['responses'].append({'method': method, 'path': path,
                    'http_status': response.status_code, 'seconds': elapsed,
                    'rpc_requests': rpc_calls[0] - before, 'body': response.json()})
            return response

        def csrf(session):
            request(session, 'GET', '/api/accounts/csrf/')

        def mark(number, description):
            evidence['journeys'][str(number)] = {'outcome': 'PASS', 'evidence': description}
            print(f'PASS HTTP journey {number}: {description}', flush=True)

        def verify(reference, expected='VALID'):
            result = request(public, 'GET', f'/api/verification/passport/{reference}/', capture=True).json()
            assert result['status'] == expected, result['status']
            assert not any(key in json.dumps(result) for key in
                ('http.student@', 'Synthetic Student', 'first_name', 'last_name', 'evidence_reference', 'storage_key'))
            return result

        def drain():
            call_command('run_backend_workers', once=True, stdout=StringIO())
            # Repeated command invocations recreate worker state; only durable
            # database jobs and original signed bytes bridge these cycles.
            for _ in range(8):
                call_command('process_blockchain_proofs', stdout=StringIO())
                pending = PassportAnchor.objects.exclude(state__in=['CONFIRMED', 'FAILED'])
                if not pending.exists():
                    break
                fixture.local.mine_blocks(1)
                # Normal production retry delay is retained. Tests make the
                # current run's jobs due without changing signed evidence.
                pending.update(next_attempt_at=None)
            assert not PassportAnchor.objects.exclude(state='CONFIRMED').exists()

        def import_course(course, event):
            workbook = Workbook()
            workbook.active.append(list(REQUIRED_FIELDS))
            values = dict(external_student_id=student.external_student_id,
                course_id=course, completion_status='completed', grade=90,
                passed=True, completion_date='2026-10-20', source_event_id=event)
            workbook.active.append([values[key] for key in REQUIRED_FIELDS])
            content = BytesIO()
            workbook.save(content)
            workbook.close()
            return request(registrar, 'POST', '/api/integrations/import/excel/', capture=True,
                files={'file': ('synthetic.xlsx', content.getvalue(),
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}).json()

        csrf(learner)
        request(learner, 'POST', '/api/accounts/otp/request/', expected=202, json={'email': student.email})
        code = re.search(r'code is: ([0-9]{6})', mail.outbox[-1].body).group(1)
        request(learner, 'POST', '/api/accounts/otp/verify/', json={'email': student.email, 'code': code})
        me = request(learner, 'GET', '/api/accounts/me/', capture=True).json()
        assert me['student_association'] == 'linked' and me['capabilities'] == []
        request(learner, 'GET', f'/api/student/credentials/{fixture.credential.pk}/', expected=404)
        mark(1, 'OTP, rotated session, restored account context, cross-student credential denial')
        assert request(learner, 'GET', '/api/student/passport/', capture=True).json() == {'passport': None}
        assert not DigitalPassport.objects.filter(student=student).exists()
        unissued_student = Student.objects.create(external_student_id='HTTP-UNISSUED-001',
            first_name='Unissued', last_name='Synthetic', email='http.unissued@btu.edu.ge',
            program='AI', education_level='Bachelor', student_status='Active')
        unissued, _ = get_or_create_passport(student_id=unissued_student.pk)
        verify(unissued.public_reference, 'NOT_ISSUED')
        verify(uuid4(), 'NOT_FOUND')
        mark(2, 'Login without achievements creates no Passport identity or issued version')

        for session, user in ((registrar, admin), (reader, limited)):
            csrf(session)
            summary = request(session, 'POST', '/api/accounts/login/', capture=True,
                json={'email': user.email, 'password': password}).json()
            if user == limited:
                assert summary['capabilities'] == ['view_student_records']
            else:
                assert 'manage_legal_identity' in summary['capabilities']
                assert 'manage_passport_lifecycle' in summary['capabilities']
        assert import_course('AI-101', 'HTTP-COMPLETION-1')['result']['issued'] == 1
        passport = DigitalPassport.objects.get(student=student, status='ACTIVE')
        first_identity, first_version = passport.pk, passport.latest_version_id
        pending = request(learner, 'GET', '/api/student/passport/', capture=True).json()
        assert pending['status'] == 'PENDING_BLOCKCHAIN'
        drain()
        assert verify(passport.public_reference)['blockchain']['blockchain_verified'] is True
        mark(3, 'Authorized Excel import creates credential, identity, version, PDF and confirmed Anvil proof')

        assert import_course('AI-201', 'HTTP-COMPLETION-2')['result']['issued'] == 1
        drain()
        passport.refresh_from_db()
        assert passport.pk == first_identity and passport.latest_version_id != first_version
        assert passport.versions.count() == 2
        request(learner, 'GET', '/api/student/dashboard/', capture=True)
        request(learner, 'GET', '/api/student/credentials/', capture=True)
        request(learner, 'GET', '/api/student/passport/versions/', capture=True)
        request(learner, 'GET', '/api/student/passport/pdf/status/', capture=True)
        request(learner, 'GET', '/api/integrations/course-recommendations/', capture=True)
        request(registrar, 'GET', '/api/admin/students/', capture=True)
        request(registrar, 'GET', f'/api/admin/passports/?student_id={student.pk}', capture=True)
        mark(4, 'New approved completion appends immutable version under the same permanent identity')
        pdf = request(learner, 'GET', '/api/student/passport/pdf/download/').content
        uploaded = request(public, 'POST', '/api/verification/document/', capture=True,
            files={'file': ('official.pdf', pdf, 'application/pdf')}).json()
        assert uploaded['status'] == 'VALID' and uploaded['authentic'] is True
        tampered = request(public, 'POST', '/api/verification/document/', capture=True,
            files={'file': ('tampered.pdf', pdf + b'\n%tampered', 'application/pdf')}).json()
        assert tampered['authentic'] is False
        mark(5, 'Anonymous reference/PDF verification confirms exact bytes and rejects altered PDF')

        credential = Credential.objects.filter(student=student).order_by('issued_at').first()
        request(registrar, 'POST', f'/api/admin/credentials/{credential.pk}/revoke/',
            json={'reason': 'Synthetic acceptance revocation'}, capture=True)
        historical = request(public, 'POST', '/api/verification/document/', capture=True,
            files={'file': ('historical.pdf', pdf, 'application/pdf')}).json()
        assert historical['status'] == 'REVOKED' and historical['authentic'] is True
        assert historical['blockchain']['blockchain_verified'] is False
        drain()
        verify(passport.public_reference)
        mark(6, 'Credential revocation invalidates its historical snapshot; refreshed current version uses surviving evidence')

        previous_reference = passport.public_reference
        payload = dict(expected_passport_reference=str(previous_reference), first_name='Corrected',
            last_name='Legalname', idempotency_key='HTTP-NAME-CHANGE-1',
            evidence_source='BTU_REGISTRAR', evidence_reference='SYNTHETIC-APPROVAL-1',
            reason='Approved synthetic legal correction')
        lifecycle = f'/api/admin/students/{student.pk}/legal-name-change/'
        request(reader, 'POST', lifecycle, expected=403, json=payload)
        request(registrar, 'POST', lifecycle, expected=403, csrf=False, json=payload)
        changed = request(registrar, 'POST', lifecycle, json=payload, capture=True).json()
        replay = request(registrar, 'POST', lifecycle, json=payload).json()
        assert changed['event_id'] == replay['event_id']
        replacement = DigitalPassport.objects.get(student=student, status='ACTIVE')
        assert replacement.pk != first_identity
        verify(previous_reference, 'REPLACED')
        assert request(learner, 'GET', '/api/student/passport/').json()['status'] == 'PENDING_BLOCKCHAIN'
        drain()
        verify(replacement.public_reference)
        request(registrar, 'GET', f'/api/admin/passports/?student_id={student.pk}', capture=True)
        request(registrar, 'GET', f'/api/admin/passports/{first_identity}/versions/', capture=True)
        history = request(registrar, 'GET', f'/api/admin/students/{student.pk}/passport-lifecycle/', capture=True).json()
        assert history['count'] == 1
        request(learner, 'GET', f'/api/student/passport/versions/{first_version}/pdf/download/', expected=404)
        request(registrar, 'GET', f'/api/admin/passports/{first_identity}/pdf/download/')
        mark(7, 'Permissioned legal correction, CSRF, idempotent replay, on-chain cancellation dependency and historical Admin PDF')

        # A real connection failure, followed by worker command restart. No
        # mocked chain response or database confirmation flag is used.
        with socket.socket() as reserve:
            reserve.bind(('127.0.0.1', 0))
            unavailable_url = f'http://127.0.0.1:{reserve.getsockname()[1]}'
            with override_settings(PASSPORT_BLOCKCHAIN_RPC_URL=unavailable_url):
                failed = verify(replacement.public_reference, 'UNVERIFIABLE')
                assert failed['blockchain']['blockchain_verified'] is False
        before = list(PassportAnchor.objects.order_by('pk').values_list('pk', 'transaction_hash', 'nonce'))
        drain()
        assert before == list(PassportAnchor.objects.order_by('pk').values_list('pk', 'transaction_hash', 'nonce'))
        verify(replacement.public_reference)
        mark(9, 'Real RPC outage fails closed; restarted worker retains transaction hashes/nonces and restores live verification')

        request(reader, 'POST', f'/api/admin/passports/{replacement.pk}/revoke/', expected=403,
            json={'idempotency_key': 'DENIED', 'reason': 'Denied'})
        request(registrar, 'POST', f'/api/admin/passports/{replacement.pk}/revoke/', capture=True,
            json={'idempotency_key': 'HTTP-REVOKE-1', 'reason': 'Synthetic institutional revocation'})
        drain()
        result = verify(replacement.public_reference, 'REVOKED')
        assert result['blockchain']['blockchain_verified'] is False
        mark(8, 'Authorized Passport revocation is terminal and retains historical cryptographic evidence')
        request(public, 'GET', '/api/admin/passports/', expected=403)
        request(learner, 'POST', lifecycle, expected=403, json=payload)
        request(learner, 'POST', '/api/accounts/logout/', expected=204)
        request(learner, 'GET', '/api/student/dashboard/', expected=403)
        mark(10, 'Anonymous/Student lifecycle denial, least privilege, public privacy and logout invalidation')
        assert import_course('AI-101', 'HTTP-COMPLETION-1')['result']['skipped'] == 1
        assert Credential.objects.filter(student=student).count() == 2
        assert DigitalPassport.objects.filter(student=student).count() == 2
        mark(11, 'Repeated import is idempotent; no duplicate credentials or reactivation of revoked identity')
        assert set(evidence['journeys']) == set(map(str, range(1, 12)))
        assert PassportDocument.objects.filter(passport_version__passport__student=student, status='ISSUED').count() == 4
        connections.close_all()

    output = os.environ.get('BACKEND_CONTRACT_OUTPUT')
    if output:
        destination = Path(output).resolve()
        if destination.parent != (ROOT / 'ops').resolve() or destination.name != 'BACKEND_CONTRACT_EXAMPLES.json':
            raise RuntimeError('Contract output must be the explicit repository handoff artifact.')
        destination.write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')
    print('PASS all 11 real HTTP/Anvil journeys; owned database, mail, media, server and signer removed.', flush=True)


if __name__ == '__main__':
    main()
