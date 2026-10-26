"""Run-owned HTTP acceptance resources. Never adopt or delete existing resources.

SIGINT/SIGTERM unwind finally blocks. A forced OS kill cannot run Python cleanup;
preserve unidentified leftovers for investigation rather than deleting them.
"""
from contextlib import ExitStack
import os
import secrets
import signal
import subprocess
import tempfile


def test_database_name(label):
    return 'test_owned_' + label + '_' + secrets.token_hex(12)


class DisposableRun(ExitStack):
    def __enter__(self):
        super().__enter__()
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous = signal.getsignal(sig)
            self.callback(signal.signal, sig, previous)
            signal.signal(sig, self._interrupt)
        return self

    @staticmethod
    def _interrupt(signum, frame):
        raise KeyboardInterrupt('Test run interrupted')

    def database(self):
        from django.conf import settings
        from django.db import connections
        from django.test import override_settings
        from django.test.utils import setup_databases, teardown_databases

        if (set(connections) != {'default'}
                or any(os.environ.get(key) for key in ('PGHOSTADDR', 'PGSERVICE', 'PGSERVICEFILE', 'PGOPTIONS'))
                or any(cache.get('BACKEND') != 'django.core.cache.backends.locmem.LocMemCache'
                       for cache in settings.CACHES.values())):
            raise RuntimeError('Refusing shared connections, cache or libpq overrides')
        config = connections['default'].settings_dict
        name = config['TEST']['NAME']
        if (config['ENGINE'] != 'django.db.backends.postgresql'
                or config['HOST'] != '127.0.0.1' or not name.startswith('test_owned_')
                or config.get('OPTIONS', {}).keys() - {'connect_timeout'}):
            raise RuntimeError('Refusing non-owned test database configuration')
        connection = connections['default']
        original_name = config['NAME']
        with connection._nodb_cursor() as cursor:
            cursor.execute('SELECT 1 FROM pg_database WHERE datname = %s', [name])
            if cursor.fetchone():
                raise RuntimeError('Refusing to adopt an existing test database')
        directory = self.enter_context(tempfile.TemporaryDirectory(prefix='passport-owned-test-'))
        self.enter_context(override_settings(MEDIA_ROOT=directory, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'))
        # CREATE is atomic: a collision fails without adopting/deleting anything.
        with connection._nodb_cursor() as cursor:
            cursor.execute('CREATE DATABASE ' + connection.ops.quote_name(name))
        db = [(connection, original_name, True)]
        def dispose():
            connections.close_all()
            # setup may have failed before Django changed NAME. Disposal must
            # still target the database created here, never the maintenance DB.
            connection.settings_dict['NAME'] = name
            teardown_databases(db, verbosity=0)
            with connections['default']._nodb_cursor() as cursor:
                cursor.execute('SELECT 1 FROM pg_database WHERE datname = %s', [name])
                if cursor.fetchone():
                    raise RuntimeError('Owned test database cleanup failed')
            connections.close_all()
        self.callback(dispose)
        # keepdb applies only to the empty database we just created. Register
        # disposal before migrations so failed setup is also cleaned up.
        setup_databases(verbosity=0, interactive=False, keepdb=True)
        def clear_memory():
            from django.core import mail
            from django.core.cache import caches
            if hasattr(mail, 'outbox'):
                mail.outbox.clear()
            for cache in caches.all():
                # Test settings use process-local memory only.
                if cache.__class__.__module__ != 'django.core.cache.backends.locmem':
                    raise RuntimeError('Refusing to clear a shared test cache')
                cache.clear()
        self.callback(clear_memory)
        return db

    def server(self, server, thread):
        def stop():
            try:
                server.shutdown()
            finally:
                server.server_close()
                thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError('Owned HTTP server did not stop')
        self.callback(stop)

    def fixture(self, fixture):
        def clean():
            if not fixture.doCleanups():
                raise RuntimeError('Synthetic fixture cleanup reported a failure')
        self.callback(clean)

    def command(self, command, *, timeout=900, **kwargs):
        """Reap only the child created here, including timeout and interruption."""
        if os.name != 'nt':
            kwargs['start_new_session'] = True
        child = subprocess.Popen(command, **kwargs)
        try:
            output, error = child.communicate(timeout=timeout)
            return subprocess.CompletedProcess(command, child.returncode, output, error)
        finally:
            if child.poll() is None:
                if os.name == 'nt':
                    # PID is still live and belongs to this Popen. Include
                    # Vite/compiler grandchildren, never match process names.
                    subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    os.killpg(child.pid, signal.SIGKILL)
                if child.poll() is None:
                    child.kill()
            child.wait()
