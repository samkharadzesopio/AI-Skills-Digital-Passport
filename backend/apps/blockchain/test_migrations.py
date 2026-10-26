import hashlib
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from apps.passports.test_documents import DocumentDataMixin
from apps.passports.document_services import generate_passport_document


class PassportMigrationTests(DocumentDataMixin,TransactionTestCase):
    def test_existing_identity_snapshots_documents_and_bytes_survive_schema_evolution(self):
        document=generate_passport_document(passport_version_id=self.version.pk,storage=self.storage)
        with self.storage.open(document.storage_key,'rb') as stream:
            original=stream.read()
        original_hash=hashlib.sha256(original).hexdigest()
        original_reference=self.version.passport.public_reference
        executor=MigrationExecutor(connection)
        leaves=executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([('passports','0006_snapshot_subcategory')])
            old=executor.loader.project_state([('passports','0006_snapshot_subcategory')]).apps
            Passport=old.get_model('passports','DigitalPassport')
            self.assertEqual(Passport.objects.get(pk=self.version.passport_id).public_reference,original_reference)
        finally:
            MigrationExecutor(connection).migrate(leaves)
        from apps.passports.models import DigitalPassport, PassportVersion, PassportDocument
        passport=DigitalPassport.objects.get(pk=self.version.passport_id)
        self.assertEqual(passport.status,'ACTIVE')
        self.assertEqual(passport.first_issued_at,self.version.issued_at)
        self.assertEqual(passport.legal_name_snapshot,{'first_name':'PDF','last_name':'Student'})
        self.assertEqual(PassportVersion.objects.get(pk=self.version.pk).content_sha256,self.version.content_sha256)
        self.assertEqual(PassportDocument.objects.get(pk=document.pk).pdf_sha256,original_hash)
        with self.storage.open(document.storage_key,'rb') as stream:
            self.assertEqual(stream.read(),original)
