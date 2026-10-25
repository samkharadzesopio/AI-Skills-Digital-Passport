from datetime import timedelta
from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from apps.credentials.services import issue_credential, revoke_credential
from apps.passports.document_services import generate_passport_document
from apps.passports.services import publish_passport_version
from apps.passports.test_documents import DocumentDataMixin
from .passport_service import PassportVerificationService
from .document_service import DocumentVerificationService


@override_settings(VERIFICATION_TRUSTED_ISSUER_REFERENCES=['BTU-UNIVERSITY'])
class PassportPublicTests(DocumentDataMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient(enforce_csrf_checks=True)

    def url(self, reference=None, kind='passport'):
        return f'/api/verification/{kind}/{reference or self.version.passport.public_reference}/'

    def test_reference_and_version_routes_are_public_and_private_data_absent(self):
        for url in [self.url(), self.url(self.version.public_reference, 'passport-version')]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['status'], 'VALID')
            self.assertEqual(response.json()['credential_counts']['VALID'], 1)
            self.assertEqual(response['Cache-Control'], 'no-store')
            for secret in [self.student.email, str(self.student.pk), str(self.version.pk), str(self.credential.pk)]:
                self.assertNotIn(secret, response.content.decode())

    def test_invalid_unknown_and_internal_ids_are_not_verification_references(self):
        for reference in ['bad-reference', self.student.pk, self.version.pk, self.version.passport.pk]:
            response = self.client.get(self.url(reference))
            self.assertEqual(response.json()['status'], 'NOT_FOUND')

    def test_reference_verification_uses_two_queries(self):
        with self.assertNumQueries(2):
            result = PassportVerificationService().verify(self.version.passport.public_reference)
        self.assertEqual(result['status'], 'VALID')

    def test_historical_version_is_outdated_but_credentials_current(self):
        self.student.first_name = 'New profile'
        self.student.save()
        publish_passport_version(student_id=self.student.pk, event_key='PUBLIC-NEW-VERSION')
        result = PassportVerificationService().verify(self.version.public_reference, kind='version')
        self.assertEqual((result['status'], result['credential_status']), ('OUTDATED', 'VALID'))
        self.assertFalse(result['is_latest'])

    @override_settings(CREDENTIAL_REVOCATION_AUTHORIZER=lambda actor, credential: 'synthetic-actor')
    def test_revoked_credential_invalidates_reference_and_pdf_even_before_refresh(self):
        document = generate_passport_document(passport_version_id=self.version.pk, storage=self.storage)
        with self.storage.open(document.storage_key, 'rb') as stream:
            content = stream.read()
        # Hold the outbox pending to prove verification never depends on refresh timing.
        with patch('apps.credentials.passport_refresh.process_passport_refresh_event'):
            revoke_credential(public_reference=self.credential.public_reference, actor=None, reason='Synthetic revocation')
        result = PassportVerificationService().verify(self.version.public_reference, kind='version')
        self.assertEqual(result['status'], 'REVOKED')
        pdf = DocumentVerificationService().verify(SimpleUploadedFile('old.pdf', content, content_type='application/pdf'))
        self.assertEqual(pdf['status'], 'REVOKED')
        self.assertTrue(pdf['authentic'])

    def test_expired_credential_is_reported_without_rewriting_history(self):
        now = timezone.now()
        expiring = issue_credential(issuer_reference=self.issuer.reference, idempotency_key='PUBLIC-EXPIRY',
            achievement_ids=list(self.credential.achievements.values_list('pk', flat=True)),
            issued_at=now-timedelta(minutes=1), expires_at=now+timedelta(minutes=1))
        version, _ = publish_passport_version(student_id=self.student.pk, event_key='WITH-EXPIRY')
        result = PassportVerificationService(clock=lambda: now+timedelta(minutes=2)).verify(version.public_reference, kind='version')
        self.assertEqual(result['status'], 'EXPIRED')
        self.assertEqual(result['credential_counts'], {'VALID': 1, 'REVOKED': 0, 'EXPIRED': 1, 'INVALID': 0})

    @override_settings(VERIFICATION_TRUSTED_ISSUER_REFERENCES=[])
    def test_untrusted_issuer_is_never_valid(self):
        result = PassportVerificationService().verify(self.version.public_reference, kind='version')
        self.assertEqual(result['status'], 'INVALID')

    def test_empty_issued_snapshot_is_unverifiable(self):
        from apps.students.models import Student
        empty = Student.objects.create(external_student_id='EMPTY-SYNTHETIC', first_name='Empty', last_name='Test', email='empty@example.org', program='AI', education_level='Bachelor', student_status='Active')
        version, _ = publish_passport_version(student_id=empty.pk, event_key='EMPTY')
        self.assertEqual(PassportVerificationService().verify(version.public_reference, kind='version')['status'], 'UNVERIFIABLE')

    def test_snapshot_work_is_bounded(self):
        with patch('apps.verification.passport_service.MAX_PUBLIC_CREDENTIALS', 0):
            self.assertEqual(PassportVerificationService().verify(self.version.public_reference, kind='version')['status'], 'UNVERIFIABLE')

    def test_reference_rate_limit_is_shared_by_version_route_and_logs_no_identifiers(self):
        for _ in range(60):
            self.assertEqual(self.client.get(self.url()).status_code, 200)
        with self.assertLogs('apps.verification.views', level='WARNING') as captured:
            response = self.client.get(self.url(self.version.public_reference, 'passport-version'))
        self.assertEqual(response.status_code, 429)
        self.assertNotIn(str(self.version.public_reference), '\n'.join(captured.output))
        self.assertNotIn(self.student.email, '\n'.join(captured.output))

    def test_uploaded_expired_snapshot_does_not_remain_valid(self):
        now = timezone.now()
        expiry = now + timedelta(minutes=1)
        issue_credential(issuer_reference=self.issuer.reference, idempotency_key='PDF-EXPIRY',
            achievement_ids=list(self.credential.achievements.values_list('pk', flat=True)),
            issued_at=now-timedelta(minutes=1), expires_at=expiry)
        version, _ = publish_passport_version(student_id=self.student.pk, event_key='PDF-WITH-EXPIRY')
        document = generate_passport_document(passport_version_id=version.pk, storage=self.storage)
        with self.storage.open(document.storage_key, 'rb') as stream:
            content = stream.read()
        with patch('apps.verification.passport_service.timezone.now', return_value=expiry+timedelta(seconds=1)):
            result = DocumentVerificationService().verify(SimpleUploadedFile('expiring.pdf', content, content_type='application/pdf'))
        self.assertEqual(result['status'], 'EXPIRED')
        self.assertTrue(result['authentic'])

    def test_draft_verification_reference_is_not_authentic(self):
        from apps.passports.models import PassportVersion
        draft = PassportVersion.objects.create(passport=self.version.passport, version_number=2, student_snapshot={})
        result = PassportVerificationService().verify(draft.public_reference, kind='version')
        self.assertEqual(result['status'], 'UNVERIFIABLE')
        self.assertFalse(result['authentic'])

    def test_exact_reference_printed_in_existing_pdf_is_supported(self):
        document = generate_passport_document(passport_version_id=self.version.pk, storage=self.storage)
        import pymupdf
        with self.storage.open(document.storage_key, 'rb') as stream:
            with pymupdf.open(stream=stream.read(), filetype='pdf') as pdf:
                text = '\n'.join(page.get_text() for page in pdf)
        printed = f'passport-version:{self.version.public_reference}'
        self.assertIn(printed, text)
        self.assertEqual(self.client.get(self.url(printed)).json()['status'], 'VALID')
        self.assertEqual(self.client.get(self.url(printed, 'passport-version')).json()['status'], 'VALID')
        self.assertEqual(self.client.get(self.url('student:' + str(self.student.pk))).json()['status'], 'NOT_FOUND')
