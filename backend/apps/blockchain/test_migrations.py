import hashlib
import secrets
from django.db import connection
from django.db import IntegrityError, transaction
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
        original_snapshot=dict(self.version.student_snapshot)
        original_storage=document.storage_key
        # Backfill must use the frozen first issued identity, even if the
        # authoritative Student record already contains a later correction.
        self.student.first_name='Later authoritative name'
        self.student.save(update_fields=['first_name'])
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
        self.assertEqual(PassportVersion.objects.get(pk=self.version.pk).student_snapshot,original_snapshot)
        self.assertEqual(passport.student_id,self.student.pk)
        self.assertEqual(passport.public_reference,original_reference)
        self.assertEqual(PassportDocument.objects.get(pk=document.pk).storage_key,original_storage)
        self.assertEqual(PassportDocument.objects.get(pk=document.pk).pdf_sha256,original_hash)
        with self.storage.open(document.storage_key,'rb') as stream:
            self.assertEqual(stream.read(),original)

    def test_historical_schema_insert_and_admin_grants_survive_upgrade(self):
        from apps.accounts.models import User
        from apps.accounts.authorization import admin_capabilities
        admin=User.objects.create_admin_user(email='migration.reader@btu.edu.ge',
            password=secrets.token_urlsafe(32),permission_codenames={'view_student_records'})
        executor=MigrationExecutor(connection)
        leaves=executor.loader.graph.leaf_nodes()
        # Exactly the pre-blockchain integration migration leaves. The new
        # dependency graph un-applies only lifecycle/proof/permission additions.
        baseline=[leaf for leaf in leaves if leaf[0] not in {'blockchain','passports','accounts'}]
        baseline += [('passports','0006_snapshot_subcategory'),('accounts','0006_deferredmail_securityaudit')]
        try:
            executor.migrate(baseline)
            historical=executor.loader.project_state(baseline).apps
            Student=historical.get_model('students','Student')
            Passport=historical.get_model('passports','DigitalPassport')
            student=Student.objects.create(external_student_id='MIGRATION-LEGACY-NO-LOGIN',
                first_name='Legacy',last_name='Synthetic',email='migration.student@btu.edu.ge',
                program='AI',education_level='Bachelor',student_status='Active')
            passport=Passport.objects.create(student_id=student.pk)
            student_id,passport_id,reference=student.pk,passport.pk,passport.public_reference
        finally:
            MigrationExecutor(connection).migrate(leaves)
        from apps.passports.models import DigitalPassport
        from apps.students.models import Student
        restored=DigitalPassport.objects.get(pk=passport_id)
        self.assertEqual(restored.student_id,student_id)
        self.assertEqual(restored.public_reference,reference)
        self.assertEqual(restored.legal_name_snapshot,{'first_name':'Legacy','last_name':'Synthetic'})
        self.assertIsNone(restored.latest_version_id)
        self.assertIsNone(restored.first_issued_at)
        self.assertEqual(len(restored.chain_salt),32)
        self.assertEqual(Student.objects.get(pk=student_id).external_student_id,'MIGRATION-LEGACY-NO-LOGIN')
        self.assertFalse(User.objects.filter(student_id=student_id).exists())
        self.assertEqual(admin_capabilities(User.objects.get(pk=admin.pk)),['view_student_records'])
        with self.assertRaises(IntegrityError),transaction.atomic():
            DigitalPassport.objects.create(student_id=student_id)
        self.assertEqual(DigitalPassport.objects.filter(student_id=student_id).count(),1)
