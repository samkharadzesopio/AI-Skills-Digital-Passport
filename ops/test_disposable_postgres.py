"""Exercise real database/media teardown on failure and interruption."""
import os
from pathlib import Path
import threading
from unittest.mock import patch
from wsgiref.simple_server import make_server

from disposable_tests import DisposableRun, test_database_name

os.environ['DJANGO_SETTINGS_MODULE'] = 'apps.integrations.postgres_test_settings'
os.environ['INTEGRATION_TEST_DB_NAME'] = test_database_name('failure')
import django
django.setup()
from django.conf import settings
from django.db import connections
from django.core.wsgi import get_wsgi_application
from apps.api.test_pdf import PassportPDFAPITests

with patch.dict(os.environ, {'PGHOSTADDR': '203.0.113.1'}):
    try:
        with DisposableRun() as resources:
            resources.database()
    except RuntimeError:
        pass
    else:
        raise AssertionError('libpq redirection was accepted')

connection = connections['default']
name = test_database_name('setup_failure')
connection.settings_dict['TEST']['NAME'] = name
try:
    with patch('django.test.utils.setup_databases', side_effect=RuntimeError('Synthetic migration failure')):
        with DisposableRun() as resources:
            resources.database()
except RuntimeError:
    pass
else:
    raise AssertionError('Setup failure was not propagated')
with connection._nodb_cursor() as cursor:
    cursor.execute('SELECT 1 FROM pg_database WHERE datname = %s', [name])
    assert cursor.fetchone() is None
connection.close()

for failure in (RuntimeError, KeyboardInterrupt):
    connection = connections['default']
    name = test_database_name('failure')
    connection.settings_dict['TEST']['NAME'] = name
    try:
        with DisposableRun() as resources:
            resources.database()
            fixture = PassportPDFAPITests()
            resources.fixture(fixture)
            fixture.setUp()
            media = Path(fixture.directory.name)
            for artifact in ('synthetic.pdf', 'upload.xlsx', 'message.otp', 'session'):
                (media / artifact).write_text('synthetic')
            server = make_server('127.0.0.1', 0, get_wsgi_application())
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            resources.server(server, thread)
            raise failure()
    except failure:
        pass
    assert not thread.is_alive()
    assert not media.exists()
    with connection._nodb_cursor() as cursor:
        cursor.execute('SELECT 1 FROM pg_database WHERE datname = %s', [name])
        assert cursor.fetchone() is None
    connection.close()

# A pre-existing database must be preserved even when its name looks test-owned.
name = test_database_name('existing')
connection.settings_dict['TEST']['NAME'] = name
with connection._nodb_cursor() as cursor:
    cursor.execute('CREATE DATABASE ' + connection.ops.quote_name(name))
try:
    try:
        with DisposableRun() as resources:
            resources.database()
    except RuntimeError:
        pass
    else:
        raise AssertionError('Existing database was adopted')
    with connection._nodb_cursor() as cursor:
        cursor.execute('SELECT 1 FROM pg_database WHERE datname = %s', [name])
        assert cursor.fetchone()
finally:
    # This regression itself created this database; use Django disposal.
    from django.test.utils import teardown_databases
    original = connection.settings_dict['NAME']
    connection.close()
    connection.settings_dict['NAME'] = name
    teardown_databases([(connection, original, True)], verbosity=0)
    connection.close()
from config.foundation_test_runner import FoundationPostgresRunner
assert FoundationPostgresRunner(verbosity=0).run_tests(['config.test_local_dev']) == 0
print('PASS failure/interruption: fixture accounts/domain records, PDFs/uploads/OTPs/sessions, server and DB disposed; existing DB refused and preserved.')
