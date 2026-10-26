import unittest
from django.core.exceptions import ImproperlyConfigured
from .local_dev_policy import local_database


class LocalDevelopmentBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.database = {'ENGINE': 'django.db.backends.postgresql', 'HOST': '127.0.0.1', 'NAME': 'btu_passport_local', 'OPTIONS': {'sslmode': 'require'}}

    def test_local_profile_is_explicit_and_does_not_mutate_production_configuration(self):
        result = local_database(self.database, enabled='1', debug=True)
        self.assertEqual(result['OPTIONS']['sslmode'], 'disable')
        self.assertEqual(self.database['OPTIONS']['sslmode'], 'require')

    def test_production_and_implicit_activation_are_rejected(self):
        for enabled, debug in [(None, True), ('true', True), ('1', False)]:
            with self.subTest(enabled=enabled, debug=debug), self.assertRaises(ImproperlyConfigured):
                local_database(self.database, enabled=enabled, debug=debug)

    def test_remote_wrong_database_and_connection_overrides_are_rejected(self):
        for changes in [{'HOST': 'remote.example'}, {'HOST': ''}, {'NAME': 'production'}, {'ENGINE': 'django.db.backends.sqlite3'}, {'OPTIONS': {'hostaddr': '203.0.113.1'}}, {'OPTIONS': {'service': 'production'}}]:
            with self.subTest(changes=changes), self.assertRaises(ImproperlyConfigured):
                local_database({**self.database, **changes}, enabled='1', debug=True)
