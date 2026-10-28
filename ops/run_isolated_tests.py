"""Provision and stop a fresh PostgreSQL cluster for automated tests.

Usage: python ops/run_isolated_tests.py [--full]
Use --spreadsheet --ui-http --browser-http for focused local website acceptance.
Use --manual-demo for a fresh local recording session; quit to remove owned data.
Requires PostgreSQL binaries on PATH or PASSPORT_PG_BIN. Never adopts a cluster.
All logs, databases and uploads are under the newly allocated temporary directory.
"""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

from disposable_tests import DisposableRun

ROOT = Path(__file__).resolve().parents[1]


def child_console_flags(*, interactive=False):
    # CREATE_NO_WINDOW is suitable for owned background tools, but detaches
    # the Windows console needed by the manual child's input()/live output.
    if os.name == 'nt' and not interactive:
        return {'creationflags': subprocess.CREATE_NO_WINDOW}
    return {}


def main():
    binary = Path(os.environ.get('PASSPORT_PG_BIN', 'C:/Program Files/PostgreSQL/18/bin'))
    def pg(name):
        return str(binary / (name + ('.exe' if os.name == 'nt' else '')))
    with DisposableRun() as run:
        temporary = tempfile.TemporaryDirectory(prefix='passport-pg-owned-')
        directory = Path(temporary.name)
        running = False
        def remove_directory():
            if running:
                temporary._finalizer.detach()
                raise RuntimeError(f'Preserved owned cluster with unverified shutdown: {directory}')
            temporary.cleanup()
            if directory.exists():
                raise RuntimeError(f'Owned test artifacts remain: {directory}')
            print('PASS cleanup: owned cluster stopped and temporary directory removed.', flush=True)
        run.callback(remove_directory)
        data = directory / 'data'
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            port = probe.getsockname()[1]
        flags = child_console_flags()
        def command(args, *, interactive=False, **kwargs):
            print('RUN ' + ' '.join(map(str, args)), flush=True)
            if 'stdout' not in kwargs:
                kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            result = run.command(args, **child_console_flags(interactive=interactive), **kwargs)
            if result.stdout:
                print(result.stdout, flush=True)
            if result.returncode:
                raise RuntimeError('Isolated test command failed (exit %d)' % result.returncode)
        with (directory / 'postgres.log').open('w') as log:
            command([pg('initdb'), '-D', str(data), '-U', 'postgres', '--auth=trust', '--no-locale', '--encoding=UTF8'], stdout=log, stderr=log)
            # Only this newly initialized cluster may be stopped by this run.
            def stop():
                nonlocal running
                result = subprocess.run([pg('pg_ctl'), '-D', str(data), '-m', 'immediate', '-w', 'stop'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
                if result.returncode:
                    raise RuntimeError('Owned PostgreSQL did not stop; preserve cluster for review')
                running = False
            run.callback(stop)
            running = True
            command([pg('pg_ctl'), '-D', str(data), '-l', str(directory / 'server.log'), '-o', f'-h 127.0.0.1 -p {port}', '-w', 'start'], stdout=log, stderr=log)
            env = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith(('PG', 'PASSPORT_BLOCKCHAIN_', 'DJANGO_'))}
            env.update(FOUNDATION_TEST_PG_HOST='127.0.0.1', FOUNDATION_TEST_PG_PORT=str(port), FOUNDATION_TEST_PG_PASSWORD='', AUTH_TEST_PG_PORT=str(port), PYTHONDONTWRITEBYTECODE='1')
            command([sys.executable, 'ops/test_disposable_tests.py'], cwd=ROOT, env=env)
            command([sys.executable, 'ops/test_disposable_postgres.py'], cwd=ROOT, env=env)
            command([sys.executable, 'backend/manage.py', 'check', '--settings=apps.integrations.postgres_test_settings'], cwd=ROOT, env=env)
            command([sys.executable, 'backend/manage.py', 'makemigrations', '--check', '--dry-run', '--settings=apps.integrations.postgres_test_settings'], cwd=ROOT, env=env)
            if '--spreadsheet' in sys.argv:
                command([sys.executable, 'backend/manage.py', 'test', 'apps.integrations.test_spreadsheet_mapping', 'apps.integrations.test_spreadsheet_migrations', '--settings=apps.integrations.postgres_test_settings', '--verbosity=1'], cwd=ROOT, env=env)
                command([sys.executable, 'ops/test_spreadsheet_e2e.py'], cwd=ROOT, env=env)
            if '--full' in sys.argv or '--backend' in sys.argv:
                command([sys.executable, 'backend/manage.py', 'test', 'apps.api', 'apps.integrations', 'apps.skills', 'apps.credentials', 'apps.passports', 'apps.students', 'apps.accounts', 'apps.verification', 'apps.blockchain', '--settings=apps.integrations.postgres_test_settings', '--verbosity=1'], cwd=ROOT, env=env, timeout=1800)
            if '--chain-http' in sys.argv:
                command([sys.executable, 'ops/test_backend_chain_e2e.py'], cwd=ROOT, env=env)
            if '--full' in sys.argv or '--ui-http' in sys.argv:
                for label in ('backend_chain', 'verification', 'student', 'admin'):
                    command([sys.executable, f'ops/test_{label}_e2e.py'], cwd=ROOT, env=env)
            if '--browser-http' in sys.argv:
                command([sys.executable, 'ops/test_live_browser_e2e.py'], cwd=ROOT, env=env)
            if '--manual-demo' in sys.argv or '--demo-smoke' in sys.argv:
                mode = '--manual-demo' if '--manual-demo' in sys.argv else '--demo-smoke'
                # Inherit the operator terminal so URLs/input are live. Only
                # this explicit interactive mode has no test-command deadline.
                command([sys.executable, '-u', 'ops/test_live_browser_e2e.py', mode],
                        cwd=ROOT, env=env, stdout=None, stderr=None,
                        interactive=mode == '--manual-demo',
                        timeout=None if mode == '--manual-demo' else 900)
        run.close()
        if directory.exists():
            raise RuntimeError('Owned temporary cluster directory remains')


if __name__ == '__main__':
    main()
