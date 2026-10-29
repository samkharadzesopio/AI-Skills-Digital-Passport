"""Fail-closed boundary for the explicitly selected local development profile."""
from copy import deepcopy
from django.core.exceptions import ImproperlyConfigured


def local_database(database, *, enabled, debug):
    if enabled != '1' or debug is not True:
        raise ImproperlyConfigured('Local development requires BTU_LOCAL_DEVELOPMENT=1 and DJANGO_DEBUG=true.')
    if (
        database.get('ENGINE') != 'django.db.backends.postgresql'
        or database.get('HOST') not in ('127.0.0.1', 'localhost', '::1')
        or database.get('NAME') != 'btu_passport_local'
        or any(key in database.get('OPTIONS', {}) for key in ('service', 'host', 'hostaddr', 'dbname'))
    ):
        raise ImproperlyConfigured('Local development requires loopback PostgreSQL database btu_passport_local.')
    result = deepcopy(database)
    result.setdefault('OPTIONS', {})['sslmode'] = 'disable'
    result['OPTIONS']['connect_timeout'] = 5
    return result
