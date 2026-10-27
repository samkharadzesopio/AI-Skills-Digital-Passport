"""Final semantics, shared work limits and controlled original-byte recovery."""
from copy import copy
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.api.serializers import PassportSerializer
from apps.credentials.services import revoke_credential
from apps.passports.document_services import generate_passport_document
from apps.passports.models import DigitalPassport, PassportVersion
from apps.passports.services import publish_passport_version
from apps.students.models import Student
from apps.verification.blockchain_policy import apply_passport_proof
from .chain import ProofError
from .middleware import BlockchainRPCBudgetMiddleware
from .models import PassportAnchor, ProofObservation, SignerNonce
from .rpc import BoundedHTTPProvider, RPCDeadlineExceeded
from .services import _sign, document_proof, process_anchor, recover_signed_operation
from .tests import ChainDataMixin


@override_settings(PASSPORT_BLOCKCHAIN_ENFORCE=True)
class FinalStatusTests(SimpleTestCase):
    def proof(self, status='CONFIRMED', **extra):
        return dict(status=status, historical_blockchain_authentic=True,
                    blockchain_verified=True, institutional_issuer_approved=True,
                    issuer_key_authorized=True, **extra)

    def private(self, proof, status='ACTIVE'):
        obj = SimpleNamespace(status=status, latest_version_id='issued', _api_blockchain_proof=proof)
        return PassportSerializer().get_status(obj)

    def public(self, proof, status='VALID'):
        return apply_passport_proof(dict(status=status, is_latest=True), proof)['status']

    def test_only_actual_pending_can_produce_pending_root(self):
        for nested, root in [('PENDING_BLOCKCHAIN', 'PENDING_BLOCKCHAIN'), ('FAILED', 'UNVERIFIABLE'),
                             ('NOT_CONFIGURED', 'UNVERIFIABLE'), ('UNAVAILABLE', 'UNVERIFIABLE'),
                             ('UNVERIFIABLE', 'UNVERIFIABLE'), ('CONFIRMED', 'BLOCKCHAIN_VERIFIED')]:
            self.assertEqual(self.private(self.proof(nested)), root)
            self.assertEqual(self.public(self.proof(nested)), 'VALID' if root == 'BLOCKCHAIN_VERIFIED' else root)

    def test_lifecycle_and_credential_terminals_precede_confirmation(self):
        for terminal in ('REPLACED', 'REVOKED'):
            for field in ('passport_status', 'onchain_status'):
                proof = self.proof(**{field: terminal})
                self.assertEqual(self.private(proof), terminal)
                self.assertEqual(self.public(proof), terminal)
                self.assertFalse(proof['blockchain_verified'])
        for terminal in ('REVOKED', 'EXPIRED', 'INVALID'):
            proof = self.proof(registry_status=terminal)
            self.assertEqual(self.private(proof), terminal)
            self.assertEqual(self.public(proof, terminal), terminal)
            self.assertFalse(proof['blockchain_verified'])

    def test_missing_institutional_approval_is_never_positive(self):
        proof = self.proof()
        proof['institutional_issuer_approved'] = False
        self.assertEqual(self.private(proof), 'UNVERIFIABLE')
        self.assertEqual(self.public(proof), 'UNVERIFIABLE')
        self.assertFalse(proof['blockchain_verified'])

    def test_missing_signer_authorization_is_never_positive(self):
        proof = self.proof()
        proof['issuer_key_authorized'] = False
        self.assertEqual(self.private(proof), 'UNVERIFIABLE')
        self.assertEqual(self.public(proof), 'UNVERIFIABLE')
        self.assertFalse(proof['blockchain_verified'])

    def test_empty_membership_is_not_current_certification(self):
        result = dict(status='UNVERIFIABLE', is_latest=True, credential_membership_empty=True)
        self.assertEqual(apply_passport_proof(result, self.proof())['status'], 'UNVERIFIABLE')

    def test_current_verdict_requires_current_not_only_historical_proof(self):
        proof = self.proof()
        proof['blockchain_verified'] = False
        self.assertEqual(self.private(proof), 'UNVERIFIABLE')
        self.assertEqual(self.public(proof), 'UNVERIFIABLE')
        self.assertEqual(self.public(proof, 'OUTDATED'), 'OUTDATED')

    def test_many_records_share_one_request_deadline(self):
        provider = BoundedHTTPProvider('http://127.0.0.1:8545')
        response = Mock(status_code=200)
        context = Mock()
        context.__enter__ = Mock(return_value=response)
        context.__exit__ = Mock(return_value=False)
        clock = [0.0]
        def read(*args, **kwargs):
            clock[0] += 2
            return b'{}' if int(clock[0]) % 4 else b''
        response.raw.read1.side_effect = read
        def many_records(request):
            failures = 0
            for _ in range(25):
                try:
                    provider._make_request('eth_chainId', b'{}')
                except RPCDeadlineExceeded:
                    failures += 1
            return failures
        with patch('apps.blockchain.rpc.time.monotonic', side_effect=lambda: clock[0]), \
                patch.object(provider._session, 'post', return_value=context) as post, \
                patch.object(provider._session, 'close') as close:
            failures = BlockchainRPCBudgetMiddleware(many_records)(None)
        self.assertEqual(failures, 24)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(clock[0], 6)
        close.assert_called_once_with()


class FinalRecoveryTests(ChainDataMixin, TransactionTestCase):
    def recover(self, row):
        return recover_signed_operation(row.pk, expected_transaction_hash=row.transaction_hash)

    def test_onchain_revocation_precedes_private_and_public_confirmation(self):
        self.assertEqual(self.process(), 'CONFIRMED')
        row = PassportAnchor.objects.get(pk=self.anchor.pk)
        tx = self.gateway.contract.functions.revokePassport(bytes.fromhex(row.passport_key)).transact(
            {'from': self.signer.address})
        self.web3.eth.wait_for_transaction_receipt(tx, timeout=5, poll_latency=.02)
        current = DigitalPassport.objects.get(pk=self.version.passport_id)
        self.assertEqual(current.status, 'ACTIVE')
        self.assertEqual(PassportSerializer(current, context={'now': timezone.now()}).data['status'], 'REVOKED')
        public = APIClient().get(f'/api/verification/passport/{current.public_reference}/').json()
        self.assertEqual(public['status'], 'REVOKED')
        self.assertTrue(public['blockchain']['historical_blockchain_authentic'])
        self.assertFalse(public['blockchain']['blockchain_verified'])

    def test_dropped_original_transaction_recovers_without_key_or_new_nonce(self):
        row = _sign(self.anchor, self.gateway, self.signer)
        frozen = (bytes(row.signed_transaction), row.transaction_hash, row.nonce)
        with patch('apps.blockchain.services.load_signer', side_effect=AssertionError('No key needed')):
            self.assertIn(self.recover(row), ('CONFIRMED', 'SUBMITTED'))
            self.assertEqual(self.process(), 'CONFIRMED')
            self.assertEqual(self.recover(row), 'CONFIRMED')
        row.refresh_from_db()
        self.assertEqual((bytes(row.signed_transaction), row.transaction_hash, row.nonce), frozen)
        self.assertEqual(SignerNonce.objects.get().next_nonce, row.nonce + 1)
        self.assertEqual(ProofObservation.objects.filter(operation=row, status='OPERATOR_REBROADCAST').count(), 1)

    def test_recovery_requires_reviewed_hash_and_current_fee_limit(self):
        row = _sign(self.anchor, self.gateway, self.signer)
        with self.assertRaisesRegex(ProofError, 'REVIEWED_TRANSACTION_REQUIRED'):
            recover_signed_operation(row.pk, expected_transaction_hash='0x' + '0' * 64)
        with override_settings(PASSPORT_BLOCKCHAIN_MAX_GAS_PRICE_WEI=1), \
                self.assertRaisesRegex(ProofError, 'GAS_PRICE_LIMIT'):
            self.recover(row)
        changed = copy(row)
        changed.commitment = 'b' * 64
        with self.assertRaisesRegex(ProofError, 'SIGNED_TRANSACTION_REVIEW_REQUIRED'):
            self.gateway.validate_signed(changed)
        self.assertFalse(ProofObservation.objects.filter(status='OPERATOR_REBROADCAST').exists())

    def test_worker_respects_reduced_fee_cap_without_losing_signed_attempt(self):
        row = _sign(self.anchor, self.gateway, self.signer)
        frozen = bytes(row.signed_transaction)
        with override_settings(PASSPORT_BLOCKCHAIN_MAX_GAS_PRICE_WEI=1):
            self.assertEqual(process_anchor(row.pk), 'SIGNED')
        row.refresh_from_db()
        self.assertEqual(row.error_code, 'GAS_PRICE_LIMIT')
        self.assertTrue(row.retryable)
        self.assertEqual(bytes(row.signed_transaction), frozen)
        self.assertIn(self.recover(row), ('CONFIRMED', 'SUBMITTED'))
        self.assertEqual(self.process(), 'CONFIRMED')

    def test_underpriced_original_recovers_when_network_fee_becomes_acceptable(self):
        row = _sign(self.anchor, self.gateway, self.signer)
        frozen = bytes(row.signed_transaction)
        self.local.rpc('anvil_setNextBlockBaseFeePerGas', [hex(self.web3.eth.gas_price * 4)])
        self.assertEqual(process_anchor(row.pk), 'SUBMITTED')
        self.assertFalse(document_proof(self.document.public_reference)['blockchain_verified'])
        self.local.rpc('anvil_setNextBlockBaseFeePerGas', ['0x1'])
        self.local.mine_blocks(1)
        self.assertIn(self.recover(row), ('CONFIRMED', 'SUBMITTED'))
        self.assertEqual(self.process(), 'CONFIRMED')
        row.refresh_from_db()
        self.assertEqual(bytes(row.signed_transaction), frozen)
        self.assertEqual(SignerNonce.objects.get().next_nonce, row.nonce + 1)

    def test_pending_foreign_transaction_cannot_be_overwritten_by_recovery(self):
        row = _sign(self.anchor, self.gateway, self.signer)
        self.local.rpc('evm_setAutomine', [False])
        try:
            other = self.signer.sign_transaction(dict(chainId=31337, nonce=row.nonce,
                to=self.web3.eth.accounts[1], value=1, gas=21000, gasPrice=self.web3.eth.gas_price))
            self.web3.eth.send_raw_transaction(other.raw_transaction)
            with self.assertRaisesRegex(ProofError, 'NONCE_CONFLICT_REVIEW_REQUIRED'):
                self.recover(row)
            row.refresh_from_db()
            self.assertEqual(row.state, 'SIGNED')
            self.assertFalse(ProofObservation.objects.filter(status='OPERATOR_REBROADCAST').exists())
        finally:
            self.local.rpc('evm_setAutomine', [True])
            self.local.mine_blocks(1)

    def test_operator_command_requires_explicit_action(self):
        row = _sign(self.anchor, self.gateway, self.signer)
        with self.assertRaises(CommandError):
            call_command('recover_blockchain_operation', str(row.pk),
                         expected_transaction_hash=row.transaction_hash, stdout=StringIO())
        self.assertFalse(ProofObservation.objects.filter(status='OPERATOR_REBROADCAST').exists())

    def test_student_without_approved_evidence_cannot_receive_initial_version(self):
        student = Student.objects.create(external_student_id='NO-APPROVED-EVIDENCE',
            first_name='Synthetic', last_name='Unapproved', email='no.evidence@btu.edu.ge',
            program=self.student.program, education_level=self.student.education_level,
            student_status=self.student.student_status)
        with self.assertRaisesRegex(ValidationError, 'approved learning evidence'):
            publish_passport_version(student_id=student.pk, event_key='NO-EVIDENCE')
        self.assertFalse(DigitalPassport.objects.filter(student=student).exists())
        self.assertEqual(PassportVersion.objects.count(), 1)

    def test_empty_refresh_after_revocation_never_restores_current_badge(self):
        self.assertEqual(self.process(), 'CONFIRMED')
        with override_settings(CREDENTIAL_REVOCATION_AUTHORIZER=lambda actor, credential: 'synthetic-local-actor'):
            revoke_credential(public_reference=self.credential.public_reference, actor=None, reason='Synthetic regression')
        current = DigitalPassport.objects.get(student=self.student, status='ACTIVE')
        self.assertNotEqual(current.latest_version_id, self.version.pk)
        self.assertEqual(current.latest_version.credential_snapshots.count(), 0)
        document = generate_passport_document(passport_version_id=current.latest_version_id, storage=self.storage)
        row = PassportAnchor.objects.get(document=document)
        self.assertEqual(self.await_operation(row.pk), 'CONFIRMED')
        proof = document_proof(document.public_reference)
        self.assertTrue(proof['historical_blockchain_authentic'])
        self.assertFalse(proof['blockchain_verified'])
        public = APIClient().get(f'/api/verification/passport/{current.public_reference}/').json()
        self.assertEqual(public['status'], 'UNVERIFIABLE')
        self.assertEqual(PassportSerializer(current, context={'now': timezone.now()}).data['status'], 'UNVERIFIABLE')
