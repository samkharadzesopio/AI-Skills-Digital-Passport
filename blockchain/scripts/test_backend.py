"""Blockchain regressions on a fresh, exclusively owned loopback PostgreSQL.

Never adopts an existing cluster/database, imports production settings, or uses
public RPC/signing configuration. Integration's newer test harness is separate.
"""
import argparse
from contextlib import ExitStack
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
LABELS = ('apps.blockchain', 'apps.api', 'apps.integrations', 'apps.skills',
          'apps.credentials', 'apps.passports', 'apps.students', 'apps.accounts',
          'apps.verification')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('labels', nargs='*')
    args = parser.parse_args()
    labels = args.labels or list(LABELS)
    if any(not any(label == app or label.startswith(app + '.') for app in LABELS) for label in labels):
        parser.error('Only supported backend test labels are allowed.')
    binaries = Path(os.environ.get('PASSPORT_PG_BIN', 'C:/Program Files/PostgreSQL/18/bin'))
    def pg(name):
        return str(binaries / (name + ('.exe' if os.name == 'nt' else '')))
    for name in ('initdb', 'pg_ctl'):
        if not Path(pg(name)).is_file():
            parser.error('Set PASSPORT_PG_BIN to installed PostgreSQL binaries.')
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    with ExitStack() as stack:
        directory = Path(tempfile.mkdtemp(prefix='passport-blockchain-owned-'))
        running = False
        def remove():
            if running:
                raise RuntimeError('Owned cluster shutdown unverified; preserving ' + str(directory))
            resolved = directory.resolve()
            if (resolved.parent != Path(tempfile.gettempdir()).resolve()
                    or not resolved.name.startswith('passport-blockchain-owned-') or directory.is_symlink()):
                raise RuntimeError('Refusing cleanup outside the owned temporary directory.')
            import shutil
            shutil.rmtree(directory)
            print('PASS cleanup: owned PostgreSQL cluster and artifacts removed.', flush=True)
        stack.callback(remove)
        def interrupt(signum, frame):
            raise KeyboardInterrupt('Interrupted; cleaning owned test resources')
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous = signal.signal(sig, interrupt)
            stack.callback(signal.signal, sig, previous)
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        data = directory / 'data'
        with (directory / 'init.log').open('w') as log:
            subprocess.run([pg('initdb'), '-D', str(data), '-U', 'postgres', '--auth=trust',
                            '--no-locale', '--encoding=UTF8'], stdout=log, stderr=log, check=True, **flags)
        def stop():
            nonlocal running
            status = subprocess.run([pg('pg_ctl'), '-D', str(data), 'status'],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
            if status.returncode == 3:
                running = False
                return
            subprocess.run([pg('pg_ctl'), '-D', str(data), '-m', 'immediate', '-w', 'stop'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, **flags)
            running = False
        stack.callback(stop)
        running = True
        subprocess.run([pg('pg_ctl'), '-D', str(data), '-l', str(directory / 'server.log'),
                        '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start'], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
        # Unique cluster, unique database, generated settings and process-local cache.
        # Never read .env or inherit libpq redirection/service/production settings.
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('PG', 'PASSPORT_BLOCKCHAIN_', 'DJANGO_'))}
        env.update(FOUNDATION_TEST_PG_HOST='127.0.0.1', FOUNDATION_TEST_PG_PORT=str(port),
                   FOUNDATION_TEST_PG_PASSWORD=secrets.token_urlsafe(24), AUTH_TEST_PG_PORT=str(port),
                   PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(directory))
        module = 'owned_blockchain_settings'
        (directory / (module + '.py')).write_text(
            "from apps.integrations.postgres_test_settings import *\n"
            "DATABASES['default']['TEST']['NAME'] = 'test_owned_" + secrets.token_hex(12) + "'\n"
            "MEDIA_ROOT = " + repr(str(directory / 'media')) + "\n"
            "EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'\n"
            "MIDDLEWARE = ['apps.blockchain.middleware.BlockchainRPCBudgetMiddleware', *MIDDLEWARE]\n",
            encoding='utf-8')
        def command(extra):
            result = subprocess.run([sys.executable, '-B', 'backend/manage.py', *extra,
                                     '--settings=' + module], cwd=ROOT, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    encoding='utf-8', errors='replace', **flags)
            print(result.stdout, flush=True)
            if result.returncode:
                raise RuntimeError('Isolated Django command failed, exit ' + str(result.returncode))
        print('Fresh owned loopback cluster; supported labels: ' + ', '.join(labels), flush=True)
        command(['check'])
        command(['makemigrations', '--check', '--dry-run'])
        command(['test', *labels, '--verbosity=1', '--noinput'])


if __name__ == '__main__':
    main()
