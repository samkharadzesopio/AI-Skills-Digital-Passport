"""Current-proof races and the additive metadata used by all Passport viewers."""
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.passports.services import publish_passport_version
from apps.verification.passport_service import PassportVerificationService
from .services import document_proof
from .metadata import network_metadata
from .tests import ChainDataMixin


class NetworkMetadataTests(SimpleTestCase):
    def test_only_amoy_hashes_produce_a_fixed_https_explorer_link(self):
        tx = '0x' + 'ab' * 32
        self.assertEqual(network_metadata(80002, tx), {
            'network': 'Polygon Amoy',
            'transaction_explorer_url': 'https://amoy.polygonscan.com/tx/' + tx,
        })
        for chain in (31337, 1337, 137, None):
            self.assertIsNone(network_metadata(chain, tx)['transaction_explorer_url'])
        for invalid in (None, '', '0x12', tx + '\n', tx + '?redirect=https://invalid.test',
                        'https://invalid.test', 'javascript:alert(1)'):
            self.assertIsNone(network_metadata(80002, invalid)['transaction_explorer_url'])


class CurrentProofIntegrationTests(ChainDataMixin, TransactionTestCase):
    def test_version_updated_during_assessment_cannot_keep_current_badge(self):
        self.assertEqual(self.process(), 'CONFIRMED')
        verify = PassportVerificationService.verify

        def refresh_before_registry_check(service, *args, **kwargs):
            self.student.program = 'Updated assessed AI program'
            self.student.save(update_fields=['program'])
            publish_passport_version(student_id=self.student.pk, event_key='concurrent-version-refresh')
            return verify(service, *args, **kwargs)

        with patch.object(PassportVerificationService, 'verify', refresh_before_registry_check):
            proof = document_proof(self.document.public_reference)
        self.assertEqual(proof['status'], 'CONFIRMED')
        self.assertEqual(proof['registry_status'], 'OUTDATED')
        self.assertEqual(proof['latest_version'], 2)
        self.assertTrue(proof['historical_blockchain_authentic'])
        self.assertFalse(proof['blockchain_verified'])

    def test_all_existing_viewer_apis_retain_authoritative_network_metadata(self):
        self.assertEqual(self.process(), 'CONFIRMED')
        self.student.email = 'network.viewer@btu.edu.ge'
        self.student.save(update_fields=['email'])
        user = User.objects.create_user(email=self.student.email, student=self.student, is_email_verified=True)
        student = APIClient()
        student.force_authenticate(user)
        public = APIClient()
        responses = [
            student.get('/api/student/passport/'),
            student.get('/api/student/dashboard/'),
            student.get('/api/student/passport/pdf/status/'),
            public.get(f'/api/verification/passport/{self.version.passport.public_reference}/'),
            public.get(f'/api/verification/passport-version/{self.version.public_reference}/'),
            public.post('/api/verification/document/', {'file': SimpleUploadedFile(
                'passport.pdf', self.pdf_bytes(), content_type='application/pdf')}, format='multipart'),
            public.get(f'/api/verification/blockchain/document/{self.document.public_reference}/'),
        ]
        hashes = set()
        for index, response in enumerate(responses):
            with self.subTest(endpoint=index):
                self.assertEqual(response.status_code, 200)
                data = response.json()
                if index == 1:
                    data = data['passport']
                proof = data if index == 6 else data['blockchain']
                self.assertEqual(proof['network'], 'Anvil')
                self.assertEqual(proof['environment'], 'LOCAL_ANVIL')
                self.assertEqual(proof['chain_id'], 31337)
                self.assertIsNone(proof['transaction_explorer_url'])
                self.assertEqual(proof['required_confirmations'], 1)
                self.assertGreaterEqual(proof['confirmations'], 1)
                self.assertTrue(proof['blockchain_verified'])
                hashes.add(proof['transaction_hash'])
        self.anchor.refresh_from_db()
        self.assertEqual(hashes, {self.anchor.transaction_hash})

    def test_pending_and_unconfigured_metadata_do_not_imply_confirmation(self):
        pending = document_proof(self.document.public_reference)
        self.assertEqual(pending['network'], 'Anvil')
        self.assertEqual(pending['required_confirmations'], 1)
        self.assertIsNone(pending['transaction_hash'])
        self.assertIsNone(pending['transaction_explorer_url'])
        self.assertFalse(pending['blockchain_verified'])
        with override_settings(PASSPORT_BLOCKCHAIN_ENABLED=False):
            disabled = document_proof(self.document.public_reference)
        self.assertIsNone(disabled['network'])
        self.assertIsNone(disabled['transaction_explorer_url'])
        self.assertFalse(disabled['blockchain_verified'])
