"""Console for owned synthetic recordings, not an application control endpoint."""
import contextvars
import argparse
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit
from uuid import UUID

import requests


class DemoClient:
    def __init__(self, base):
        parsed = urlsplit(base)
        if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port
                or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ValueError('Owned loopback origin required.')
        self.base = base
        self.session = requests.Session()
        self.session.trust_env = False

    def close(self):
        self.session.close()

    def request(self, method, path, *, expected=200, csrf=True, **kwargs):
        headers = {}
        if method != 'GET' and csrf:
            self.request('GET', '/api/accounts/csrf/')
            headers['X-CSRFToken'] = self.session.cookies.get('csrftoken', '')
        response = self.session.request(method, self.base + path, headers=headers, timeout=15,
                                        allow_redirects=False, **kwargs)
        if response.status_code != expected:
            # Never expose provider text, submitted credentials or server dumps.
            raise RuntimeError(f'Demo request returned HTTP {response.status_code}; expected {expected}.')
        return response


def recording_session(owned, fixture, base, mailbox, *, smoke=False, stop_file=None):
    # Keep Django imports inside the owned server path. The separate-terminal
    # controller below uses authenticated HTTP only, never database settings.
    from django.core.management import call_command
    from django.db import connections
    from apps.blockchain.services import process_batch
    from apps.blockchain.chain import configured_gateway
    from apps.blockchain.models import PassportAnchor
    from apps.blockchain.policy import load_policy
    from apps.passports.models import DigitalPassport
    from apps.integrations.spreadsheet_automation import poll_due_sources
    # These resources were already created and guarded by DisposableRun. Never
    # load production/local .env or reuse the old database, state or issuer key.
    fixture.local.rpc('evm_setIntervalMining', [1])
    private = json.loads(mailbox.read_text())
    admin, public = DemoClient(base), DemoClient(base)
    owned.callback(admin.close)
    owned.callback(public.close)
    admin.request('POST', '/api/accounts/login/', json={
        'email': private['adminEmail'], 'password': private['adminPassword']})

    stop = threading.Event()
    errors = []
    context = contextvars.copy_context()
    def worker():
        try:
            while not stop.is_set():
                try:
                    # Existing durable workers, unchanged retry/nonce/receipt
                    # rules. Do not fast-forward confirmations or rewrite jobs.
                    call_command('run_backend_workers', once=True, stdout=StringIO())
                    if stop_file is not None:
                        poll_due_sources(limit=5)
                    process_batch()
                except Exception:
                    if not errors:
                        print('Demo worker unavailable; inspect the actual public verdict.', flush=True)
                    errors.append(True)
                stop.wait(1)
        finally:
            connections.close_all()
    thread = threading.Thread(target=lambda: context.run(worker), daemon=True)
    thread.start()
    def stop_worker():
        stop.set()
        thread.join(timeout=45)
        if thread.is_alive():
            raise RuntimeError('Owned demo worker did not stop; inspect owned resources.')
    owned.callback(stop_worker)

    def current():
        return DigitalPassport.objects.get(student=fixture.student, status='ACTIVE')

    def verify(reference, expected=None):
        result = public.request('GET', f'/api/verification/passport/{reference}/').json()
        if expected is not None and result['status'] != expected:
            raise AssertionError('Unexpected public lifecycle verdict.')
        return result

    def await_valid(reference):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            result = verify(reference)
            if result['status'] == 'VALID':
                proof = result['blockchain']
                assert proof['blockchain_verified'] is True
                assert proof['environment'] == 'LOCAL_ANVIL' and proof['chain_id'] == 31337
                assert proof['confirmations'] >= proof['required_confirmations'] == 3
                assert proof['transaction_explorer_url'] is None
                return result
            time.sleep(1)
        raise RuntimeError('Confirmation deadline expired; no successful proof is claimed.')

    reference = current().public_reference
    await_valid(reference)
    print(f'LOCAL ANVIL RECORDING READY — synthetic data, chain 31337, 3 confirmations\n'
          f'Student login: {base}/student/login\nAdmin login: {base}/admin/login\n'
          f'Public verification: {base}/verify/qr/passport:{reference}\n'
          f'Private login/OTP file (open privately; never paste or record): {mailbox}\n'
          'Commands: status, replace, revoke, quit. Changes affect this temporary demo only.\n'
          'quit removes this session; a new run creates new identities/transactions.', flush=True)

    def action(command):
        nonlocal reference
        # A second-terminal controller may already have changed the identity.
        latest = DigitalPassport.objects.filter(student=fixture.student).order_by('-created_at').first()
        if latest:
            reference = latest.public_reference
        if command == 'replace':
            old = reference
            old_passport = current()
            admin.request('POST', f'/api/admin/students/{fixture.student.pk}/legal-name-change/', json={
                'expected_passport_reference': str(old), 'first_name': 'Corrected', 'last_name': 'Demo',
                'idempotency_key': f'synthetic-name-{old}', 'evidence_source': 'BTU_REGISTRAR',
                'evidence_reference': 'SYNTHETIC-RECORDING-APPROVAL', 'reason': 'Synthetic recording correction'})
            verify(old, 'REPLACED')
            reference = current().public_reference
            assert current().pk != old_passport.pk
        elif command == 'revoke':
            passport = current()
            admin.request('POST', f'/api/admin/passports/{passport.pk}/revoke/', json={
                'idempotency_key': f'synthetic-revoke-{reference}', 'reason': 'Synthetic recording revocation'})
            verify(reference, 'REVOKED')
        elif command != 'status':
            raise ValueError('Use status, replace, revoke or quit.')
        result = verify(reference)
        print(f'Public verdict: {result["status"]}; '
              f'current blockchain verified: {result.get("blockchain", {}).get("blockchain_verified", False)}\n'
              f'{base}/verify/qr/passport:{reference}', flush=True)

    if smoke:
        for forbidden in ('https://example.invalid', 'http://127.0.0.1:8000/private',
                          'http://user:password@127.0.0.1:8000'):
            try:
                DemoClient(forbidden)
            except ValueError:
                pass
            else:
                raise AssertionError('Unsafe demo target accepted.')
        learner = DemoClient(base)
        owned.callback(learner.close)
        learner.request('POST', '/api/accounts/otp/request/', expected=202, json={'email': private['studentEmail']})
        otp = json.loads(mailbox.read_text())['otp']
        learner.request('POST', '/api/accounts/otp/verify/', json={'email': private['studentEmail'], 'code': otp})
        assert learner.request('GET', '/api/student/passport/').json()['status'] == 'BLOCKCHAIN_VERIFIED'
        pdf = learner.request('GET', '/api/student/passport/pdf/download/').content
        assert pdf.startswith(b'%PDF-')
        for data, expected in ((pdf, 'VALID'), (pdf + b'\n%tampered', 'UNVERIFIABLE')):
            result = public.request('POST', '/api/verification/document/', csrf=False,
                                    files={'file': ('synthetic.pdf', data, 'application/pdf')}).json()
            assert result['status'] == expected
        path = f'/api/admin/passports/{current().pk}/revoke/'
        learner.request('POST', path, expected=403, json={'idempotency_key': 'denied', 'reason': 'denied'})
        admin.request('POST', path, expected=403, csrf=False, json={'idempotency_key': 'denied', 'reason': 'denied'})
        old = reference
        def control(command):
            result = owned.command([sys.executable, '-B', str(Path(__file__).resolve()),
                                    '--url', base, '--fixture', str(mailbox), command],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=45)
            assert result.returncode == 0, 'Separate-terminal control failed.'
            assert private['adminPassword'] not in result.stdout + result.stderr
            return json.loads(result.stdout)
        assert control('status')['status'] == 'VALID'
        replacement = control('replace')
        reference = replacement['passport_reference']
        await_valid(reference)
        verify(old, 'REPLACED')
        # The original prompt follows the externally changed identity too.
        action('status')
        assert control('revoke')['status'] == 'REVOKED'
        assert verify(reference, 'REVOKED')['blockchain']['blockchain_verified'] is False
        deadline = time.monotonic() + 90
        operations = PassportAnchor.objects.filter(passport__student=fixture.student)
        while operations.exclude(state='CONFIRMED').exists():
            if operations.filter(state='FAILED').exists() or time.monotonic() >= deadline:
                raise RuntimeError('Cancellation did not confirm; no chain success is claimed.')
            time.sleep(1)
        gateway = configured_gateway(load_policy())
        for operation in operations.filter(operation_type__in=['REPLACE', 'REVOKE']):
            assert gateway.verify(operation)['confirmations'] >= 3
        assert verify(reference, 'REVOKED')['blockchain']['onchain_status'] == 'REVOKED'
        assert not errors
        print('PASS manual demo smoke: real OTP, PDF, tampering, CSRF/ownership, replacement and confirmed revocation.', flush=True)
        return

    if stop_file is not None:
        print(f'Persistent local review session. Create {stop_file} to stop and clean only owned resources.', flush=True)
        while not stop_file.exists():
            time.sleep(1)
        return

    while True:
        try:
            command = input('demo> ').strip().lower()
        except EOFError:
            break
        if command == 'quit':
            break
        try:
            action(command)
        except Exception as error:
            print(f'Command failed ({type(error).__name__}); no success is claimed.', flush=True)


def control_session(base, command, fixture_path=None):
    """Use existing permissions/CSRF on one owned synthetic session; no DB/RPC."""
    admin, public = DemoClient(base), DemoClient(base)
    try:
        if fixture_path:
            path = Path(fixture_path).resolve()
        else:
            candidates = list(Path(tempfile.gettempdir()).glob('btu-live-browser-private-*/preview-private.json'))
            if len(candidates) != 1:
                raise ValueError('One private fixture required; select --fixture explicitly.')
            path = candidates[0].resolve()
        if (path.name != 'preview-private.json' or not path.parent.name.startswith('btu-live-browser-private-')
                or path.stat().st_size > 4096):
            raise ValueError('Owned private fixture required.')
        private = json.loads(path.read_text())
        runtime = json.loads(path.with_name('preview-runtime.json').read_text())
        if (runtime.get('synthetic') is not True or private.get('adminEmail') != 'browser.admin@btu.edu.ge'
                or private.get('studentEmail') != 'browser.student@btu.edu.ge'):
            raise ValueError('Synthetic fixture required.')
        student_id = str(UUID(runtime['studentId']))
        admin.request('POST', '/api/accounts/login/', json={
            'email': private['adminEmail'], 'password': private['adminPassword']})
        summary = admin.request('GET', f'/api/admin/students/{student_id}/').json()
        if str(summary['profile']['id']) != student_id or summary['profile']['email'] != private['studentEmail']:
            raise ValueError('Fixture association mismatch.')
        passport = summary['passport']
        if not passport:
            return {'status': 'NO_ACTIVE_PASSPORT', 'changed': False}
        proof = passport.get('blockchain') or {}
        if proof.get('environment') != 'LOCAL_ANVIL' or proof.get('chain_id') != 31337:
            raise ValueError('Confirmed local target configuration required.')
        old = str(UUID(passport['public_reference']))
        if command == 'replace':
            result = admin.request('POST', f'/api/admin/students/{student_id}/legal-name-change/', json={
                'expected_passport_reference': old, 'first_name': 'Corrected', 'last_name': 'Demo',
                'idempotency_key': f'synthetic-name-{old}', 'evidence_source': 'BTU_REGISTRAR',
                'evidence_reference': 'SYNTHETIC-RECORDING-APPROVAL', 'reason': 'Synthetic recording correction'}).json()
            reference = str(UUID(result['passport']['public_reference']))
        elif command == 'revoke':
            admin.request('POST', f'/api/admin/passports/{UUID(passport["id"])}/revoke/', json={
                'idempotency_key': f'synthetic-revoke-{old}', 'reason': 'Synthetic recording revocation'})
            reference = old
        elif command == 'status':
            reference = old
        else:
            raise ValueError('Unsupported demo action.')
        result = public.request('GET', f'/api/verification/passport/{reference}/').json()
        return {'status': result['status'], 'changed': command != 'status',
                'passport_reference': reference, 'previous_passport_reference': old,
                'verification_url': f'{base}/verify/qr/passport:{reference}',
                'blockchain_verified': (result.get('blockchain') or {}).get('blockchain_verified', False)}
    finally:
        admin.close()
        public.close()


def main():
    parser = argparse.ArgumentParser(description='Control an existing owned local demo through protected APIs. Does not start or stop servers.')
    parser.add_argument('--url', required=True, help='Actual loopback website origin printed by the running session.')
    parser.add_argument('--fixture', help='Private preview-private.json path, needed only if discovery is ambiguous.')
    parser.add_argument('command', choices=['status', 'replace', 'revoke'])
    args = parser.parse_args()
    try:
        print(json.dumps(control_session(args.url, args.command, args.fixture), indent=2), flush=True)
        return 0
    except Exception:
        # Never echo credentials, provider responses, file contents or URLs
        # carrying userinfo supplied accidentally by an operator.
        print(json.dumps({'status': 'CONTROL_UNAVAILABLE', 'changed': None,
                          'action_outcome': 'NOT_CONFIRMED_CHECK_PUBLIC_STATUS'}), flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
