"""Forward migration rehearsal against owned fresh and populated integration schemas."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase

from apps.blockchain.tests import ChainDataMixin
from apps.integrations.models import ImportRun


class SpreadsheetMigrationTests(ChainDataMixin, TransactionTestCase):
    def test_existing_student_credential_passport_pdf_and_signed_chain_history_preserved(self):
        self.assertEqual(self.await_operation(self.anchor.pk, gateway=self.gateway, signer=self.signer), 'CONFIRMED')
        with self.storage.open(self.document.storage_key, 'rb') as stream:
            original_pdf = stream.read()
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        # Include actual custom table names (credentials, digital_passports, etc.)
        # and every join table, rather than relying on Django app-name prefixes.
        protected = [t for t in connection.introspection.table_names()
                     if t != 'django_migrations' and not t.startswith('integrations_spreadsheet')]

        def snapshot():
            with connection.cursor() as cursor:
                result = {}
                for table in protected:
                    cursor.execute(f'SELECT to_jsonb(t)::text FROM {connection.ops.quote_name(table)} t ORDER BY to_jsonb(t)::text')
                    result[table] = cursor.fetchall()
                return result

        try:
            executor.migrate([('integrations', '0002_importrun_and_more')])
            historical = executor.loader.project_state([('integrations', '0002_importrun_and_more')]).apps
            run = historical.get_model('integrations', 'ImportRun').objects.create(source='BTU_EXCEL', state='FAILED', summary={'error': 'SYNTHETIC_EXISTING_HISTORY'})
            before = snapshot()
        finally:
            MigrationExecutor(connection).migrate(leaves)
        self.assertEqual(snapshot(), before)
        self.assertEqual(ImportRun.objects.get(pk=run.pk).summary, {'error': 'SYNTHETIC_EXISTING_HISTORY'})
        with self.storage.open(self.document.storage_key, 'rb') as stream:
            self.assertEqual(stream.read(), original_pdf)
        self.assertEqual(self.await_operation(self.anchor.pk, gateway=self.gateway, signer=self.signer), 'CONFIRMED')

    def test_fresh_install_has_new_tables_and_integrity_triggers(self):
        tables = connection.introspection.table_names()
        for name in ('spreadsheetprofile', 'spreadsheetpreview', 'spreadsheetaward'):
            self.assertIn('integrations_' + name, tables)
        with connection.cursor() as cursor:
            cursor.execute("SELECT tgname FROM pg_trigger WHERE tgname LIKE 'spreadsheet_%_guard'")
            self.assertEqual({r[0] for r in cursor.fetchall()}, {'spreadsheet_profile_guard', 'spreadsheet_preview_guard', 'spreadsheet_award_guard'})
