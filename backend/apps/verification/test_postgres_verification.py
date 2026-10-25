from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import AuthRateLimitBucket
from apps.credentials.services import revoke_credential
from apps.passports.document_services import generate_passport_document
from apps.passports.services import publish_passport_version
from apps.passports.test_documents import DocumentDataMixin
from .document_service import DocumentVerificationService, MAX_PDF_SIZE
from .services import CredentialVerificationService


@override_settings(VERIFICATION_TRUSTED_ISSUER_REFERENCES=['PDF-ISSUER'])
class PostgreSQLVerificationTests(DocumentDataMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.client = APIClient(enforce_csrf_checks=True)

    def credential_url(self, reference=None):
        return f'/api/verification/{reference or self.credential.public_reference}/'

    def pdf_bytes(self, version=None):
        document = generate_passport_document(passport_version_id=(version or self.version).pk, storage=self.storage)
        with self.storage.open(document.storage_key, 'rb') as f:
            return f.read()

    def upload(self, content, **kwargs):
        return self.client.post('/api/verification/document/', {
            'file': SimpleUploadedFile('../../passport.pdf', content, content_type='application/pdf'),
        }, format='multipart', **kwargs)

    def test_public_reference_valid_and_private_data_absent(self):
        result = self.client.get(self.credential_url())
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['status'], 'VALID')
        self.assertEqual(result.json()['source'], 'POSTGRESQL_CREDENTIAL_REGISTRY')
        self.assertEqual(set(result.json()), {'credential_id', 'status', 'verified', 'source'})
        self.assertNotIn(str(self.student.pk), result.content.decode())
        self.assertNotIn(self.student.email, result.content.decode())

    def test_internal_uuid_and_malformed_reference_are_not_public_ids(self):
        for reference in [self.credential.pk, 'not-a-uuid']:
            self.assertEqual(self.client.get(self.credential_url(reference)).json()['status'], 'NOT_FOUND')

    def test_trust_configuration_fails_closed(self):
        for approved in [[], ['OTHER'], 'PDF-ISSUER', None]:
            with override_settings(VERIFICATION_TRUSTED_ISSUER_REFERENCES=approved):
                self.assertEqual(CredentialVerificationService().verify(self.credential.public_reference)['status'], 'INVALID')

    def test_expiry_and_future_issue_time(self):
        # Existing immutable facts stay unchanged; injected clock tests time semantics.
        service = CredentialVerificationService(clock=lambda: self.credential.issued_at - timedelta(seconds=1))
        self.assertEqual(service.verify(self.credential.public_reference)['status'], 'INVALID')
        from apps.credentials.services import issue_credential
        expiry = self.now + timedelta(hours=1)
        expiring = issue_credential(issuer_reference=self.issuer.reference, idempotency_key='EXPIRES',
                                   achievement_ids=list(self.credential.achievements.values_list('pk', flat=True)),
                                   issued_at=self.now, expires_at=expiry)
        service = CredentialVerificationService(clock=lambda: expiry)
        self.assertEqual(service.verify(expiring.public_reference)['status'], 'EXPIRED')

    @override_settings(CREDENTIAL_REVOCATION_AUTHORIZER=lambda actor, credential: 'synthetic-test-actor')
    def test_revoked_credential(self):
        revoke_credential(public_reference=self.credential.public_reference, actor=None, reason='Synthetic test')
        self.assertEqual(self.client.get(self.credential_url()).json()['status'], 'REVOKED')

    def test_credential_lookup_is_one_query(self):
        with self.assertNumQueries(1):
            self.assertEqual(CredentialVerificationService().verify(self.credential.public_reference)['status'], 'VALID')

    def test_real_pdf_uses_existing_repository_and_no_private_response(self):
        content = self.pdf_bytes()
        result = self.upload(content)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['status'], 'VALID')
        self.assertEqual(result.json()['source'], 'POSTGRESQL_DOCUMENT_REGISTRY')
        self.assertNotIn(self.student.email, result.content.decode())
        from apps.passports.models import PassportDocument
        self.assertEqual(PassportDocument.objects.count(), 1)
        with self.assertNumQueries(2):
            self.assertEqual(DocumentVerificationService().verify(SimpleUploadedFile('x.pdf', content, content_type='application/pdf'))['status'], 'VALID')

    def test_historical_pdf_tamper_and_corruption(self):
        content = self.pdf_bytes()
        self.student.first_name = 'Updated'
        self.student.save()
        publish_passport_version(student_id=self.student.pk, event_key='PUBLIC-VERIFY-V2')
        self.assertEqual(self.upload(content).json()['status'], 'OUTDATED')
        tampered = content.replace(b'%PDF-', b'%PDF-', 1) + b'\n% tampered\n'
        self.assertEqual(self.upload(tampered).json()['status'], 'UNVERIFIABLE')
        self.assertEqual(self.upload(b'not a PDF').json()['status'], 'INVALID')
        self.assertEqual(self.upload(b'%PDF-1.4\nno ending').json()['status'], 'INVALID')

    def test_upload_and_request_size_limits(self):
        content = b'%PDF-1.4\n' + b'a' * MAX_PDF_SIZE + b'%%EOF'
        self.assertEqual(self.upload(content).status_code, 413)
        self.assertEqual(self.client.generic('POST', '/api/verification/document/', b'',
                         content_type='multipart/form-data; boundary=x', CONTENT_LENGTH=str(MAX_PDF_SIZE + 65537)).status_code, 413)

    def test_public_endpoints_ignore_bad_session_cookies(self):
        self.client.cookies['sessionid'] = 'invalid-session-cookie'
        self.assertEqual(self.client.get(self.credential_url()).status_code, 200)
        self.assertEqual(self.upload(self.pdf_bytes()).status_code, 200)

    def test_rate_limit_persists_between_clients_and_ignores_forwarded_ip(self):
        for _ in range(10):
            self.assertEqual(self.upload(b'bad').status_code, 200)
        other = APIClient()
        response = other.post('/api/verification/document/', {'file': SimpleUploadedFile('x.pdf', b'bad', content_type='application/pdf')},
                              format='multipart', HTTP_X_FORWARDED_FOR='203.0.113.123')
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
        # Credential and PDF budgets are separate.
        self.assertEqual(other.get(self.credential_url()).status_code, 200)

    def test_parallel_pdf_requests_share_database_limit(self):
        # Consume all but one allowance first.
        for _ in range(9):
            self.upload(b'bad')
        barrier = Barrier(2)
        def request(_):
            close_old_connections()
            try:
                client = APIClient()
                barrier.wait(timeout=10)
                return client.post('/api/verification/document/', {'file': SimpleUploadedFile('x.pdf', b'bad', content_type='application/pdf')}, format='multipart').status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(request, range(2))), [200, 429])
        self.assertEqual(AuthRateLimitBucket.objects.get().request_count, 10)

    def test_actual_read_is_bounded_even_when_declared_size_is_false(self):
        from io import BytesIO
        class LyingUpload(BytesIO):
            size = 10
            content_type = 'application/pdf'
        result = DocumentVerificationService().verify(LyingUpload(b'%PDF-1.4\n' + b'x' * MAX_PDF_SIZE + b'%%EOF'))
        self.assertEqual(result['status'], 'INVALID')
