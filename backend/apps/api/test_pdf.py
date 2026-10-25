import hashlib
import io
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import pymupdf
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import resolve
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import SecurityAudit, User
from apps.credentials.services import issue_credential, revoke_credential
from apps.credentials.test_support import create_test_issuer
from apps.passports.document_services import _claim_document, _request_sha256, _render_context, _version_queryset
from apps.passports.models import DigitalPassport, PassportDocument, PassportVersion
from apps.passports.services import publish_passport_version
from apps.skills.models import AchievementSourceEvent, Skill, VerifiedAchievement
from apps.students.models import Student
from passport_pdf_renderer import RENDERER_VERSION, render_passport_pdf


@override_settings(
    CREDENTIAL_REVOCATION_AUTHORIZER='apps.accounts.authorization.authorize_credential_revocation',
    PASSPORT_PDF_REQUESTS_PER_MINUTE=1000,
)
class PassportPDFAPITests(TransactionTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='private-pdf-api-')
        self.settings_override = override_settings(MEDIA_ROOT=self.directory.name)
        self.settings_override.enable()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.settings_override.disable)
        self.student = self.make_student('owner')
        self.other = self.make_student('other')
        self.user = User.objects.create_user(
            email=self.student.email, student=self.student, is_email_verified=True,
        )
        self.other_user = User.objects.create_user(
            email=self.other.email, student=self.other, is_email_verified=True,
        )
        self.admin = User.objects.create_admin_user(
            email='pdf-admin@btu.edu.ge', password='SyntheticPDFAdmin!1927',
            permission_codenames=['view_student_records', 'manage_credentials', 'revoke_credentials'],
        )
        self.skill = Skill.objects.create(
            skill_code='PDF-API', skill_name='AI Reasoning', category='AI',
            subcategory='Reasoning', description='Evaluate AI reasoning.',
            stamp_type='APPLIED', badge_asset_id='ai_applied.png',
        )
        create_test_issuer('Business and Technology University')
        self.credential = self.issue(self.student)
        self.passport = DigitalPassport.objects.get(student=self.student)
        self.version = self.passport.latest_version
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = '/api/student/passport/pdf/'
        self.admin_url = f'/api/admin/passports/{self.passport.pk}/pdf/'

    def make_student(self, name):
        return Student.objects.create(
            external_student_id=f'PDF-{name}', first_name='Synthetic', last_name=name,
            email=f'pdf-{name}@btu.edu.ge', program='AI', education_level='Bachelor',
            student_status='ACTIVE',
        )

    def issue(self, student, **kwargs):
        source = AchievementSourceEvent.objects.create(
            source='PDF_API_TEST', source_event_id=str(uuid4()), payload_sha256='b' * 64,
        )
        award = VerifiedAchievement.objects.create(
            student=student, skill=self.skill, source_event=source,
            earned_on=timezone.now().date(), verification_status='VERIFIED',
        )
        return issue_credential(
            issuer_reference='BTU-UNIVERSITY', idempotency_key=str(uuid4()),
            achievement_ids=[award.pk], **kwargs,
        )

    def generate(self, url=None):
        return self.client.post(url or self.url, {}, format='json')

    def download(self, url=None):
        response = self.client.get((url or self.url) + 'download/')
        self.assertEqual(response.status_code, 200, getattr(response, 'data', None))
        try:
            return response, b''.join(response.streaming_content)
        finally:
            response.close()

    def as_admin(self):
        self.client.force_authenticate(User.objects.get(pk=self.admin.pk))

    def assert_private_metadata(self, data):
        for key in ['storage_key', 'lease_token', 'attempt_storage_key', 'error_message', 'request_sha256', self.directory.name]:
            self.assertNotIn(key, str(data))

    def test_generation_reuses_document_and_status_contract(self):
        before = self.client.get(self.url + 'status/')
        self.assertEqual(before.status_code, 200)
        self.assertEqual(before.data['status'], 'NOT_REQUESTED')
        self.assertIsNone(before.data['document_reference'])
        first = self.generate()
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data['status'], 'ISSUED')
        self.assertTrue(first.data['available_for_download'])
        self.assertEqual(first.data['passport_version_reference'], str(self.version.public_reference))
        self.assertIsNotNone(first.data['generated_at'])
        repeated = self.generate()
        self.assertEqual(repeated.data['document_reference'], first.data['document_reference'])
        document = PassportDocument.objects.get()
        self.assertEqual(document.attempt_count, 1)
        self.assertEqual(self.client.get(self.url + 'status/').data, first.data)
        self.assert_private_metadata(first.data)

    def test_download_headers_hash_template_and_registered_public_verification(self):
        self.assertEqual(self.generate().status_code, 200)
        response, content = self.download()
        document = PassportDocument.objects.get()
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertEqual(response['Content-Disposition'], f'attachment; filename="btu-passport-{self.version.public_reference}.pdf"')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(int(response['Content-Length']), len(content))
        self.assertEqual(hashlib.sha256(content).hexdigest(), document.pdf_sha256)
        with pymupdf.open(stream=content, filetype='pdf') as pdf:
            self.assertGreaterEqual(len(pdf), 5)
            text = '\n'.join(page.get_text() for page in pdf)
            self.assertIn('BTU', text)
            self.assertIn('Synthetic', text)
            self.assertIn('AI / REASONING / APPLIED', text)
            for reference in [self.passport.public_reference, self.version.public_reference, self.credential.public_reference]:
                self.assertIn(str(reference), text)
        public = APIClient()
        result = public.post('/api/verification/document/', {
            'file': SimpleUploadedFile('passport.pdf', content, content_type='application/pdf'),
        }, format='multipart')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['status'], 'VALID')
        self.assertTrue(result.data['authentic'])
        version_result = public.get(f'/api/verification/passport-version/passport-version:{self.version.public_reference}/')
        self.assertEqual(version_result.data['status'], 'VALID')

    def test_unauthenticated_access_and_public_reference_are_not_download_authorization(self):
        self.generate()
        self.client.force_authenticate(None)
        for suffix in ['status/', 'download/']:
            self.assertEqual(self.client.get(self.url + suffix).status_code, 403)
        self.assertEqual(self.generate().status_code, 403)
        self.client.force_authenticate(self.other_user)
        for id in [self.version.pk, self.version.public_reference, self.student.pk, uuid4()]:
            base = f'/api/student/passport/versions/{id}/pdf/'
            self.assertEqual(self.generate(base).status_code, 404)
            self.assertEqual(self.client.get(base + 'status/').status_code, 404)
            self.assertEqual(self.client.get(base + 'download/').status_code, 404)

    def test_missing_passport_unissued_version_and_missing_document(self):
        self.assertEqual(self.client.get(self.url + 'download/').status_code, 404)
        self.client.force_authenticate(self.other_user)
        for suffix in ['status/', 'download/']:
            self.assertEqual(self.client.get(self.url + suffix).status_code, 404)
        self.assertEqual(self.generate().status_code, 404)
        passport = DigitalPassport.objects.create(student=self.other)
        draft = PassportVersion.objects.create(passport=passport, version_number=1)
        self.assertEqual(self.generate().status_code, 404)
        self.assertEqual(self.generate(f'/api/student/passport/versions/{draft.pk}/pdf/').status_code, 404)

    def test_historical_generation_uses_frozen_profile_classification_and_version(self):
        self.student.first_name = 'ChangedProfile'
        self.student.save()
        Skill.objects.filter(pk=self.skill.pk).update(subcategory='ChangedCatalog')
        latest, _ = publish_passport_version(student_id=self.student.pk, event_key='PDF-API-NEW')
        old_url = f'/api/student/passport/versions/{self.version.pk}/pdf/'
        self.assertEqual(self.generate(old_url).status_code, 200)
        _, content = self.download(old_url)
        with pymupdf.open(stream=content, filetype='pdf') as pdf:
            text = '\n'.join(page.get_text() for page in pdf)
        self.assertIn('Synthetic', text)
        self.assertIn('REASONING', text)
        self.assertNotIn('ChangedProfile', text)
        self.assertNotIn('ChangedCatalog', text)
        self.assertIn(str(self.version.public_reference), text)
        self.assertEqual(self.client.get(self.url + 'status/').data['status'], 'NOT_REQUESTED')
        self.assertEqual(self.client.get(self.url + 'download/').status_code, 404)
        self.assertEqual(self.generate().data['passport_version_reference'], str(latest.public_reference))

    def test_pending_and_generation_in_progress_states(self):
        request_hash = _request_sha256(self.version)
        pending = PassportDocument.objects.create(
            passport_version=self.version, generation_number=1,
            request_sha256=request_hash, renderer_version=RENDERER_VERSION,
        )
        self.assertEqual(self.client.get(self.url + 'status/').data['status'], 'PENDING')
        self.assertEqual(self.client.get(self.url + 'download/').status_code, 409)
        _claim_document(self.version.pk, request_hash, timezone.now())
        active = self.generate()
        self.assertEqual(active.status_code, 409)
        self.assertEqual(active.data['status'], 'GENERATING')
        self.assertEqual(active.data['document_reference'], str(pending.public_reference))
        self.assertEqual(active['Retry-After'], '2')
        self.assertEqual(PassportDocument.objects.get().attempt_count, 1)

    def test_failed_render_is_safe_durable_and_retriable(self):
        with patch('apps.passports.document_services.render_passport_pdf', side_effect=RuntimeError('secret C:/private/template.pdf')):
            failed = self.generate()
        self.assertEqual(failed.status_code, 503)
        self.assertEqual(failed.data['status'], 'FAILED')
        self.assertNotIn('secret', str(failed.data))
        self.assert_private_metadata(failed.data)
        status = self.client.get(self.url + 'status/').data
        self.assertEqual(status['error'], 'GENERATION_FAILED')
        recovered = self.generate()
        self.assertEqual(recovered.status_code, 200, recovered.data)
        self.assertEqual(recovered.data['document_reference'], failed.data['document_reference'])
        self.assertEqual(PassportDocument.objects.get().attempt_count, 2)

    def test_storage_failure_is_safe_and_same_document_retries(self):
        with patch('django.core.files.storage.FileSystemStorage.save', side_effect=OSError('secret storage path')):
            failed = self.generate()
        self.assertEqual(failed.status_code, 503)
        self.assertEqual(failed.data['status'], 'FAILED')
        self.assertNotIn('secret', str(failed.data))
        recovered = self.generate()
        self.assertEqual(recovered.data['document_reference'], failed.data['document_reference'])
        self.assertEqual(recovered.data['status'], 'ISSUED')

    def test_missing_stored_file_returns_safe_error(self):
        self.generate()
        with patch('django.core.files.storage.FileSystemStorage.open', side_effect=FileNotFoundError('secret C:/store.pdf')):
            response = self.client.get(self.url + 'download/')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret', str(response.data))
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_download_resource_closes_with_response(self):
        self.generate()
        handle = io.BytesIO(b'%PDF-synthetic')
        with patch('apps.api.pdf_views.open_passport_document_for_student', return_value=(PassportDocument.objects.get(), handle)):
            response = self.client.get(self.url + 'download/')
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertTrue(handle.closed)

    def test_admin_generation_download_and_audits(self):
        self.as_admin()
        result = self.generate(self.admin_url)
        self.assertEqual(result.status_code, 200, result.data)
        self.download(self.admin_url)
        self.assertTrue(SecurityAudit.objects.filter(actor=self.admin, action='AdminPDFView:POST', status_code=200).exists())
        self.assertTrue(SecurityAudit.objects.filter(actor=self.admin, action='AdminPDFView:GET', status_code=200).exists())
        self.assert_private_metadata(self.client.get(self.admin_url + 'status/').data)

    def test_admin_requires_exact_permissions_and_students_are_denied(self):
        self.assertEqual(self.generate(self.admin_url).status_code, 403)
        self.assertEqual(self.client.get(self.admin_url + 'download/').status_code, 403)
        self.admin.user_permissions.set(Permission.objects.filter(content_type__app_label='accounts', codename='view_student_records'))
        self.as_admin()
        self.assertEqual(self.generate(self.admin_url).status_code, 403)
        self.assertEqual(self.client.get(self.admin_url + 'status/').status_code, 200)
        self.admin.user_permissions.clear()
        self.as_admin()
        self.assertEqual(self.client.get(self.admin_url + 'download/').status_code, 403)
        self.assertTrue(SecurityAudit.objects.filter(actor=self.admin, action='AdminPDFView:GET', status_code=403).exists())

    def test_admin_historical_selector_is_scoped_and_identifiers_validated(self):
        self.issue(self.other)
        foreign_version = DigitalPassport.objects.get(student=self.other).latest_version_id
        self.student.program = 'New AI'; self.student.save()
        publish_passport_version(student_id=self.student.pk, event_key='ADMIN-PDF-NEW')
        self.as_admin()
        selected = self.admin_url + f'?version_id={self.version.pk}'
        result = self.generate(selected)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data['passport_version_reference'], str(self.version.public_reference))
        download = self.client.get(self.admin_url + f'download/?version_id={self.version.pk}')
        self.assertEqual(download.status_code, 200)
        download.close()
        for id in ['invalid', foreign_version, self.version.public_reference]:
            response = self.generate(self.admin_url + f'?version_id={id}')
            self.assertEqual(response.status_code, 400 if id == 'invalid' else 404)
        self.assertEqual(self.generate('/api/admin/passports/not-a-uuid/pdf/').status_code, 404)

    def test_client_storage_paths_and_identifiers_are_rejected(self):
        for key in ['student_id', 'storage_key', 'filename', 'document_reference', 'version_id']:
            self.assertEqual(self.client.post(self.url, {key: '../../secret'}, format='json').status_code, 400)
            self.assertEqual(self.client.get(self.url + 'download/', {key: '../../secret'}).status_code, 400)
        self.as_admin()
        self.assertEqual(self.generate(self.admin_url + f'?version_id={self.version.pk}&version_id={uuid4()}').status_code, 400)

    @override_settings(PASSPORT_PDF_REQUESTS_PER_MINUTE=1)
    def test_generation_budget_is_persistent_per_account(self):
        with override_settings(PASSPORT_PDF_REQUESTS_PER_MINUTE='invalid'):
            self.assertEqual(self.generate().status_code, 503)
        self.assertEqual(self.generate().status_code, 200)
        client = APIClient(); client.force_authenticate(User.objects.get(pk=self.user.pk))
        response = client.post(self.url, {}, format='json')
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)
        self.assertEqual(client.get(self.url + 'status/').status_code, 200)

    def test_concurrent_http_requests_render_once_without_open_transaction(self):
        barrier = Barrier(2)
        render_transactions = []
        def slow_renderer(data):
            render_transactions.append(connection.in_atomic_block)
            time.sleep(0.3)
            return render_passport_pdf(data)
        def request_one():
            close_old_connections()
            try:
                client = APIClient(); client.force_authenticate(User.objects.get(pk=self.user.pk))
                barrier.wait(timeout=10)
                response = client.post(self.url, {}, format='json')
                return response.status_code, response.data['document_reference']
            finally:
                close_old_connections()
        with patch('apps.passports.document_services.render_passport_pdf', side_effect=slow_renderer):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: request_one(), range(2)))
        self.assertEqual(sorted(status for status, _ in results), [200, 409])
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(render_transactions, [False])
        self.assertEqual(PassportDocument.objects.count(), 1)

    def test_session_csrf_and_non_atomic_request_marker(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user, backend='apps.accounts.authentication.StudentOTPBackend')
        self.assertEqual(client.get(self.url + 'status/').status_code, 200)
        self.assertEqual(client.post(self.url, {}, format='json').status_code, 403)
        self.assertIn('default', resolve(self.url).func._non_atomic_requests)

    def test_oversized_or_unsupported_template_text_is_reported(self):
        with override_settings(PASSPORT_PDF_MAX_SKILLS=0):
            result = self.generate()
        self.assertEqual(result.status_code, 422)
        self.assertEqual(result.data['error'], 'PDF_NOT_REPRESENTABLE')
        self.assertEqual(self.generate().status_code, 200)
        self.student.first_name = 'სახელი'; self.student.save()
        publish_passport_version(student_id=self.student.pk, event_key='FONT-LIMIT')
        result = self.generate()
        self.assertEqual(result.status_code, 422)
        self.assertFalse(result.data['available_for_download'])

    def test_revoked_historical_pdf_remains_authentic_with_current_invalidity(self):
        self.generate()
        old_url = f'/api/student/passport/versions/{self.version.pk}/pdf/'
        _, original = self.download(old_url)
        revoke_credential(public_reference=self.credential.public_reference, actor=self.admin, reason='Synthetic revocation')
        _, historical = self.download(old_url)
        self.assertEqual(historical, original)
        result = APIClient().post('/api/verification/document/', {
            'file': SimpleUploadedFile('passport.pdf', historical, content_type='application/pdf'),
        }, format='multipart')
        self.assertEqual(result.data['status'], 'REVOKED')
        self.assertTrue(result.data['authentic'])
        self.assertFalse(result.data['is_latest'])

    def test_expired_credentials_remain_visible_to_public_verification(self):
        self.issue(self.student, expires_at=timezone.now() + timedelta(days=1))
        self.generate()
        _, original = self.download()
        with patch('apps.verification.passport_service.timezone.now', return_value=timezone.now() + timedelta(days=5)):
            result = APIClient().post('/api/verification/document/', {
                'file': SimpleUploadedFile('passport.pdf', original, content_type='application/pdf'),
            }, format='multipart')
        self.assertEqual(result.data['status'], 'EXPIRED')
        self.assertTrue(result.data['authentic'])

    def test_status_query_count_does_not_grow_with_skills(self):
        self.generate()
        def queries():
            with CaptureQueriesContext(connection) as captured:
                response = self.client.get(self.url + 'status/')
                self.assertEqual(response.status_code, 200)
            return len(captured)
        before = queries()
        self.issue(self.student)
        self.assertLessEqual(queries(), before)
        self.assertLessEqual(before, 5)

    def test_prior_issued_generation_remains_downloadable_after_new_renderer_failure(self):
        first = self.generate()
        _, original = self.download()
        with patch('apps.passports.document_services.renderer_fingerprint', return_value='f' * 64):
            with patch('apps.passports.document_services.render_passport_pdf', side_effect=RuntimeError('renderer unavailable')):
                self.assertEqual(self.generate().status_code, 503)
        state = self.client.get(self.url + 'status/').data
        self.assertEqual(state['status'], 'FAILED')
        self.assertTrue(state['available_for_download'])
        self.assertEqual(state['download_document_reference'], first.data['document_reference'])
        _, fallback = self.download()
        self.assertEqual(fallback, original)
        replay = self.generate()
        self.assertEqual(replay.data['status'], 'ISSUED')
        self.assertEqual(replay.data['document_reference'], first.data['document_reference'])

    def test_all_supplement_skills_keep_categories_beyond_first_ten_cards(self):
        data = _render_context(_version_queryset().get(pk=self.version.pk))
        original = data['skills'][0]
        data['skills'] = [dict(original, name=f'Skill {index}', category=f'Category {index}', subcategory=f'Sub {index}') for index in range(11)]
        with pymupdf.open(stream=render_passport_pdf(data), filetype='pdf') as pdf:
            text = '\n'.join(page.get_text() for page in pdf)
            for page in list(pdf)[3:6]:
                for x0, y0, x1, y1, word, *_ in page.get_text('words'):
                    if word == 'Category':
                        self.assertGreaterEqual(x0, 204)
                        self.assertLessEqual(x1, 300)
                        self.assertGreaterEqual(y0, 189)
                        self.assertLessEqual(y1, 459)
        self.assertIn('Category 10', text)
        self.assertIn('Sub 10', text)

    def test_textbox_overflow_returns_422_instead_of_partial_pdf(self):
        self.student.first_name = 'W' * 90
        self.student.save()
        publish_passport_version(student_id=self.student.pk, event_key='OVERFLOW')
        result = self.generate()
        self.assertEqual(result.status_code, 422)
        self.assertEqual(result.data['status'], 'FAILED')
        self.assertEqual(result.data['error'], 'PDF_NOT_REPRESENTABLE')
