"""Real PostgreSQL + native Anvil RPC tests. No public chain or funded public key."""
import hashlib
import json
import os
import tempfile
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier
from unittest.mock import Mock, patch
from uuid import uuid4

from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, DatabaseError, connection, close_old_connections, transaction
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from eth_account import Account
from web3.exceptions import ContractLogicError as TransactionFailed
from rest_framework.test import APIClient
from web3 import Web3

from apps.credentials.services import revoke_credential
from apps.passports.document_services import generate_passport_document
from apps.passports.models import PassportDocument, PassportVersion
from apps.passports.test_documents import DocumentDataMixin
from apps.verification.document_service import DocumentVerificationService
from .chain import ChainGateway, ProofError, artifact
from .anvil_testing import AnvilChain
from .models import PassportAnchor, SignerNonce
from .policy import load_policy, load_signer
from .services import _rows, _sign, document_proof, enqueue_document, process_anchor, process_batch, reconcile_confirmed, retry_failed


class ChainDataMixin(DocumentDataMixin):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.local=AnvilChain()
        cls.addClassCleanup(cls.local.close)
        cls.web3=cls.local.web3
        cls.signer=cls.local.signer

    def setUp(self):
        super().setUp()
        self.evm=self.local
        snapshot=self.local.take_snapshot()
        self.addCleanup(self.local.revert_to_snapshot,snapshot)
        factory = self.web3.eth.contract(abi=artifact()['abi'], bytecode=artifact()['bytecode'])
        receipt = self.web3.eth.wait_for_transaction_receipt(factory.constructor(self.web3.eth.accounts[1],self.signer.address).transact({'from': self.web3.eth.accounts[1]}))
        self.key_dir = tempfile.TemporaryDirectory(prefix='btu-local-test-key-')
        self.addCleanup(self.key_dir.cleanup)
        key_path = Path(self.key_dir.name) / 'issuer.key'
        key_path.write_text(self.signer.key.hex())
        key_path.chmod(0o600)
        self.override = override_settings(
            MEDIA_ROOT=self.storage_dir.name,
            ROOT_URLCONF='config.urls',
            PASSPORT_BLOCKCHAIN_ENABLED=True,
            PASSPORT_BLOCKCHAIN_ENFORCE=True,
            PASSPORT_IDENTITY_EVIDENCE_SOURCES=['BTU_REGISTRAR'],
            PASSPORT_BLOCKCHAIN_RPC_URL=self.local.rpc_url,
            PASSPORT_BLOCKCHAIN_CHAIN_ID=self.web3.eth.chain_id,
            PASSPORT_BLOCKCHAIN_CONTRACT_ADDRESS=receipt.contractAddress,
            PASSPORT_BLOCKCHAIN_ISSUER_ADDRESS=self.signer.address,
            PASSPORT_BLOCKCHAIN_CONFIRMATIONS=1,
            PASSPORT_BLOCKCHAIN_SIGNING_KEY_FILE=str(key_path),
            VERIFICATION_TRUSTED_ISSUER_REFERENCES=['BTU-UNIVERSITY'],
        )
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.policy = load_policy()
        self.gateway = ChainGateway(self.policy, self.web3)
        self.document = generate_passport_document(passport_version_id=self.version.pk, storage=self.storage)
        self.anchor = _rows().get(document=self.document)

    def await_operation(self,operation_id,**kwargs):
        gateway=kwargs.get('gateway')
        confirmations=gateway.policy.confirmations if gateway else load_policy().confirmations
        for _ in range(20):
            state=process_anchor(operation_id,**kwargs)
            if state!='SUBMITTED' or confirmations!=1:
                return state
            row=PassportAnchor.objects.get(pk=operation_id)
            self.web3.eth.wait_for_transaction_receipt(row.transaction_hash,timeout=10,poll_latency=.02)
            time.sleep(.02)
        return state

    def process(self, **kwargs):
        return self.await_operation(self.anchor.pk,gateway=self.gateway,signer=self.signer,**kwargs)

    def pdf_bytes(self):
        return Path(self.storage.path(self.document.storage_key)).read_bytes()

class BlockchainTests(ChainDataMixin,TransactionTestCase):
    def test_pdf_issuance_enqueues_one_proof_without_rpc_or_new_passport(self):
        counts = PassportVersion.objects.count(), PassportDocument.objects.count()
        with patch('apps.blockchain.services.ChainGateway', side_effect=AssertionError('RPC forbidden')):
            self.assertEqual(enqueue_document(self.document).pk, self.anchor.pk)
            repeated = generate_passport_document(passport_version_id=self.version.pk, storage=self.storage)
        self.assertEqual(repeated.pk, self.document.pk)
        self.assertEqual(PassportAnchor.objects.count(), 1)
        self.assertEqual(counts, (PassportVersion.objects.count(), PassportDocument.objects.count()))

    def test_real_pdf_sign_broadcast_confirm_and_anonymous_verification(self):
        self.assertEqual(self.process(), 'CONFIRMED')
        self.anchor.refresh_from_db()
        self.assertEqual(self.anchor.pdf_sha256, hashlib.sha256(self.pdf_bytes()).hexdigest())
        url = f'/api/verification/blockchain/document/{self.document.public_reference}/'
        with patch('apps.blockchain.services.ChainGateway', return_value=self.gateway):
            response = APIClient().get(url)
        self.assertEqual(response.status_code, 200)
        proof = response.json()
        self.assertTrue(proof['blockchain_verified'])
        self.assertTrue(proof['issuer_key_authorized'])
        self.assertNotIn('institutional_identity_verified',proof)
        self.assertEqual(proof['environment'], 'LOCAL_ANVIL')
        self.assertEqual(proof['pdf_sha256'], self.anchor.pdf_sha256)
        self.assertEqual(response['Cache-Control'], 'no-store')
        for private in [self.student.email, self.student.external_student_id, self.document.storage_key, self.signer.key.hex()]:
            self.assertNotIn(private, response.content.decode())

    def test_insufficient_confirmations_are_pending_then_confirmed(self):
        self.gateway = ChainGateway(replace(self.policy, confirmations=3), self.web3)
        self.assertEqual(self.process(), 'SUBMITTED')
        self.assertFalse(document_proof(self.document.public_reference, gateway=self.gateway)['blockchain_verified'])
        self.evm.mine_blocks(2)
        self.assertEqual(self.process(), 'CONFIRMED')

    def test_replay_never_resigns_or_spends_a_second_transaction(self):
        self.assertEqual(self.process(), 'CONFIRMED')
        block = self.web3.eth.block_number
        first = PassportAnchor.objects.get(pk=self.anchor.pk)
        self.assertEqual(self.process(), 'CONFIRMED')
        repeated = PassportAnchor.objects.get(pk=self.anchor.pk)
        self.assertEqual(bytes(first.signed_transaction), bytes(repeated.signed_transaction))
        self.assertEqual(self.web3.eth.block_number, block)

    def test_recovery_after_broadcast_before_database_acknowledgement(self):
        signed = _sign(self.anchor, self.gateway, self.signer)
        self.gateway.broadcast(signed.signed_transaction)
        self.web3.eth.wait_for_transaction_receipt(signed.transaction_hash,timeout=5,poll_latency=.01)
        with patch.object(self.gateway, 'broadcast', side_effect=AssertionError('No second submission')):
            self.assertEqual(self.process(), 'CONFIRMED')
        self.anchor.refresh_from_db()
        self.assertEqual(self.anchor.transaction_hash, signed.transaction_hash)

    def test_recovery_after_signing_before_broadcast_uses_persisted_bytes(self):
        signed = _sign(self.anchor, self.gateway, self.signer)
        with patch('apps.blockchain.services.load_signer', side_effect=AssertionError('Do not read key again')):
            state=self.await_operation(self.anchor.pk,gateway=self.gateway)
            self.assertEqual(state,'CONFIRMED')
        self.anchor.refresh_from_db()
        self.assertEqual(bytes(signed.signed_transaction), bytes(self.anchor.signed_transaction))

    def test_uncertain_submission_is_resolved_by_receipt(self):
        broadcast = self.gateway.broadcast
        def sent_then_lost(raw):
            broadcast(raw)
            raise ConnectionError('Synthetic lost response containing secret provider details')
        with patch.object(self.gateway, 'broadcast', side_effect=sent_then_lost):
            self.assertEqual(self.process(), 'CONFIRMED')

    def test_rpc_outage_is_persistent_and_retry_recovers(self):
        with patch.object(self.gateway, 'signing_context', side_effect=ConnectionError('secret provider token')):
            self.assertEqual(self.process(), 'PENDING')
        self.anchor.refresh_from_db()
        self.assertEqual(self.anchor.error_code, 'CHAIN_OR_STORAGE_UNAVAILABLE')
        self.assertEqual(self.anchor.attempts, 1)
        self.assertIsNotNone(self.anchor.next_attempt_at)
        self.assertIsNone(self.anchor.signed_transaction)
        self.assertEqual(self.process(), 'CONFIRMED')

    def test_missing_signing_key_fails_without_reserving_a_nonce(self):
        with override_settings(PASSPORT_BLOCKCHAIN_SIGNING_KEY_FILE=''):
            self.assertEqual(process_anchor(self.anchor.pk, gateway=self.gateway), 'PENDING')
        self.anchor.refresh_from_db()
        self.assertEqual(self.anchor.error_code, 'SIGNING_CONFIGURATION')
        self.assertFalse(SignerNonce.objects.exists())

    def test_wrong_signer_and_untrusted_issuer_fail_closed(self):
        wrong = self.local.other_signer
        self.assertEqual(process_anchor(self.anchor.pk, gateway=self.gateway, signer=wrong), 'FAILED')
        self.anchor.refresh_from_db()
        self.assertEqual(self.anchor.error_code, 'UNAPPROVED_SIGNING_KEY')
        with override_settings(VERIFICATION_TRUSTED_ISSUER_REFERENCES=[]):
            proof = document_proof(self.document.public_reference, gateway=self.gateway)
        self.assertFalse(proof['blockchain_verified'])

    def test_wrong_chain_and_missing_or_wrong_contract_are_rejected(self):
        for policy, expected in [
            (replace(self.policy, chain_id=1), 'WRONG_CHAIN'),
            (replace(self.policy, contract_address=self.web3.eth.accounts[1].lower()), 'UNAPPROVED_CONTRACT_CODE'),
            (replace(self.policy, issuer_address=self.web3.eth.accounts[1].lower()), 'UNAPPROVED_ISSUER_KEY'),
        ]:
            with self.assertRaises(ProofError) as caught:
                ChainGateway(policy, self.web3).signing_context()
            self.assertEqual(caught.exception.code, expected)

    def test_contract_rejects_unauthorized_writer_and_replacement_hash(self):
        row=self.anchor
        fn=self.gateway.contract.functions.anchorPassport(bytes.fromhex(row.passport_key),bytes.fromhex(row.version_key),bytes.fromhex(row.document_key),bytes.fromhex(row.commitment))
        with self.assertRaises(TransactionFailed):
            fn.transact({'from':self.web3.eth.accounts[1]})
        self.assertEqual(self.process(),'CONFIRMED')
        with self.assertRaises(TransactionFailed):
            fn.transact({'from':self.signer.address})

    def test_tampered_pdf_cannot_inherit_the_registered_proof(self):
        self.assertEqual(self.process(), 'CONFIRMED')
        with patch('apps.blockchain.services.ChainGateway', return_value=self.gateway):
            valid = DocumentVerificationService().verify(SimpleUploadedFile('passport.pdf', self.pdf_bytes(), content_type='application/pdf'))
            tampered = DocumentVerificationService().verify(SimpleUploadedFile('changed.pdf', self.pdf_bytes() + b'\n% changed content\n', content_type='application/pdf'))
        self.assertTrue(valid['blockchain']['blockchain_verified'])
        self.assertEqual(tampered['status'], 'UNVERIFIABLE')
        self.assertFalse(tampered.get('blockchain', {}).get('blockchain_verified', False))

    def test_mismatched_commitment_document_version_and_passport_keys_fail_verification(self):
        self.assertEqual(self.process(),'CONFIRMED')
        self.anchor.refresh_from_db()
        for field in ['commitment','document_key','version_key','passport_key']:
            previous=getattr(self.anchor,field)
            setattr(self.anchor,field,'b'*64)
            with self.assertRaises(ProofError):
                self.gateway.verify(self.anchor)
            setattr(self.anchor,field,previous)

    def test_saved_confirmation_does_not_survive_chain_reorganization_or_rpc_outage(self):
        before = self.evm.take_snapshot()
        self.assertEqual(self.process(), 'CONFIRMED')
        with patch.object(self.gateway, 'verify', side_effect=ConnectionError('secret')):
            unavailable = document_proof(self.document.public_reference, gateway=self.gateway)
        self.assertFalse(unavailable['blockchain_verified'])
        self.assertEqual(unavailable['status'], 'UNAVAILABLE')
        self.evm.revert_to_snapshot(before)
        reorg = document_proof(self.document.public_reference, gateway=self.gateway)
        self.assertFalse(reorg['blockchain_verified'])
        self.assertEqual(reorg['status'], 'PENDING_BLOCKCHAIN')
        self.assertEqual(PassportAnchor.objects.get(pk=self.anchor.pk).state, 'CONFIRMED')

    def test_false_receipt_event_or_block_cannot_verify(self):
        self.assertEqual(self.process(), 'CONFIRMED')
        self.anchor.refresh_from_db()
        original = self.web3.eth.get_transaction_receipt(self.anchor.transaction_hash)
        variants = [dict(original, status=0), dict(original, blockHash=b'\x01'*32), dict(original, logs=[])]
        for receipt in variants:
            with patch.object(self.web3.eth, 'get_transaction_receipt', return_value=receipt):
                with self.assertRaises(ProofError):
                    self.gateway.verify(self.anchor)

    @override_settings(CREDENTIAL_REVOCATION_AUTHORIZER=lambda actor, credential: 'local-chain-test')
    def test_revocation_keeps_historical_integrity_but_removes_current_validity(self):
        self.assertEqual(self.process(), 'CONFIRMED')
        revoke_credential(public_reference=self.credential.public_reference, actor=None, reason='Synthetic revocation')
        with patch('apps.blockchain.services.ChainGateway', return_value=self.gateway):
            result = DocumentVerificationService().verify(SimpleUploadedFile('old.pdf', self.pdf_bytes(), content_type='application/pdf'))
        self.assertEqual(result['status'], 'REVOKED')
        self.assertTrue(result['blockchain']['historical_blockchain_authentic'])
        self.assertFalse(result['is_latest'])

    def test_confirmed_receipt_target_signature_and_nonce_are_immutable(self):
        self.assertEqual(self.process(), 'CONFIRMED')
        for changes in [{'pdf_sha256':'b'*64}, {'transaction_hash':'0x'+'a'*64}, {'nonce':999},
                        {'chain_id':80002}, {'state':'PENDING'}, {'block_number':999}]:
            with self.assertRaises(IntegrityError), transaction.atomic():
                PassportAnchor.objects.filter(pk=self.anchor.pk).update(**changes)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.anchor.delete()
        key = SignerNonce.objects.first().pk
        with self.assertRaises(IntegrityError), transaction.atomic():
            SignerNonce.objects.filter(pk=key).update(next_nonce=0)

    def test_parallel_duplicate_signing_reserves_one_nonce_and_transaction(self):
        barrier = Barrier(2)
        def sign(_):
            close_old_connections()
            try:
                row = _rows().get(pk=self.anchor.pk)
                barrier.wait(timeout=10)
                result = _sign(row, self.gateway, self.signer)
                return result.nonce, bytes(result.signed_transaction)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(sign, range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(SignerNonce.objects.first().next_nonce, results[0][0] + 1)
        self.assertEqual(self.process(), 'CONFIRMED')

    def test_parallel_different_documents_reserve_distinct_nonces(self):
        from apps.passports.services import publish_passport_version
        # Issued PDFs are immutable: changing the renderer correctly reuses the
        # original document. Publish a genuinely distinct snapshot for this test.
        self.student.program = 'Synthetic second academic program'
        self.student.save(update_fields=['program'])
        version, _ = publish_passport_version(student_id=self.student.pk, event_key='SYNTHETIC-NONCE-V2')
        second = generate_passport_document(passport_version_id=version.pk, storage=self.storage)
        self.assertNotEqual(second.pk, self.document.pk)
        ids = [self.anchor.pk, PassportAnchor.objects.get(document=second).pk]
        barrier = Barrier(2)
        def sign(anchor_id):
            close_old_connections()
            try:
                row = _rows().get(pk=anchor_id)
                barrier.wait(timeout=10)
                return _sign(row, self.gateway, self.signer).nonce
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            nonces = list(pool.map(sign, ids))
        self.assertEqual(len(set(nonces)), 2)
        for row in PassportAnchor.objects.order_by('nonce'):
            self.assertEqual(self.await_operation(row.pk, gateway=self.gateway), 'CONFIRMED')

    def test_disabled_mode_and_unknown_document_never_call_rpc(self):
        with override_settings(PASSPORT_BLOCKCHAIN_ENABLED=False), patch('apps.blockchain.services.ChainGateway', side_effect=AssertionError('Network forbidden')):
            self.assertEqual(document_proof(self.document.public_reference)['status'], 'NOT_CONFIGURED')
            self.assertEqual(document_proof(uuid4())['status'], 'NOT_FOUND')
            self.assertEqual(process_batch()['processed'], 0)
        with patch('apps.blockchain.services.ChainGateway', side_effect=AssertionError('Unknown document')):
            self.assertEqual(document_proof(uuid4())['status'], 'NOT_FOUND')

    def test_public_selectors_cannot_change_chain_or_retrieve_private_pdf(self):
        response = APIClient().get(f'/api/verification/blockchain/document/{self.document.public_reference}/', {'chain_id':'1'})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(b'%PDF', response.content)

    def test_changed_storage_bytes_are_not_anchored(self):
        Path(self.storage.path(self.document.storage_key)).write_bytes(self.pdf_bytes() + b'changed')
        self.assertEqual(self.process(), 'FAILED')
        self.anchor.refresh_from_db()
        self.assertEqual(self.anchor.error_code, 'PDF_STORAGE_MISMATCH')
        self.assertFalse(self.anchor.retryable)
        self.assertIsNone(self.anchor.signed_transaction)
        self.assertFalse(SignerNonce.objects.exists())

    def test_missing_storage_bytes_retry_without_signing_and_recover(self):
        path = Path(self.storage.path(self.document.storage_key))
        original = path.read_bytes()
        path.unlink()
        self.assertEqual(self.process(), 'PENDING')
        self.anchor.refresh_from_db()
        self.assertEqual(self.anchor.error_code, 'CHAIN_OR_STORAGE_UNAVAILABLE')
        self.assertTrue(self.anchor.retryable)
        self.assertIsNone(self.anchor.signed_transaction)
        self.assertFalse(SignerNonce.objects.exists())
        path.write_bytes(original)
        self.assertEqual(self.process(), 'CONFIRMED')

    def test_key_permissions_and_wrong_key_file_are_rejected(self):
        policy = load_policy()
        self.assertEqual(load_signer(policy).address, self.signer.address)
        path = Path(policy.signing_key_file)
        if os.name != 'nt':
            path.chmod(0o644)
            with self.assertRaises(ImproperlyConfigured):
                load_signer(policy)
            path.chmod(0o600)
        path.write_text(self.local.other_signer.key.hex())
        with self.assertRaises(ImproperlyConfigured):
            load_signer(policy)

    def test_reconciliation_recovers_a_reorganized_confirmed_transaction(self):
        before=self.evm.take_snapshot()
        self.assertEqual(self.process(),'CONFIRMED')
        self.evm.revert_to_snapshot(before)
        self.assertEqual(reconcile_confirmed(),1)
        self.assertEqual(reconcile_confirmed(),1)
        result=document_proof(self.document.public_reference)
        self.assertTrue(result['blockchain_verified'])
        self.assertGreaterEqual(self.anchor.observations.count(),2)

    def test_bounded_transient_failures_can_be_requeued_without_resigning(self):
        with patch.object(self.gateway,'signing_context',side_effect=ConnectionError('private provider error')):
            for _ in range(10):
                self.process()
        self.anchor.refresh_from_db(); self.assertEqual(self.anchor.state,'FAILED')
        self.assertEqual(retry_failed(),1)
        self.assertEqual(self.process(),'CONFIRMED')

    def test_issuer_rotation_preserves_old_proof_and_authorizes_new_operations(self):
        self.assertEqual(self.process(),'CONFIRMED')
        role=self.gateway.contract.functions.ISSUER_ROLE().call()
        self.gateway.contract.functions.grantRole(role,self.local.other_signer.address).transact({'from':self.web3.eth.accounts[1]})
        self.gateway.contract.functions.revokeRole(role,self.signer.address).transact({'from':self.web3.eth.accounts[1]})
        with override_settings(PASSPORT_BLOCKCHAIN_ISSUER_ADDRESS=self.local.other_signer.address):
            self.assertTrue(document_proof(self.document.public_reference)['blockchain_verified'])
            with patch('apps.passports.document_services.renderer_fingerprint',return_value='e'*64):
                document=generate_passport_document(passport_version_id=self.version.pk,storage=self.storage)
            operation=PassportAnchor.objects.get(document=document)
            self.assertEqual(self.await_operation(operation.pk,signer=self.local.other_signer),'CONFIRMED')

    def test_public_verification_uses_configured_registry_without_website_publication(self):
        self.assertEqual(self.process(),'CONFIRMED')
        from requests import Session
        original=Session.request
        def rpc_only(session,method,url,*args,**kwargs):
            self.assertEqual(url,self.local.rpc_url)
            return original(session,method,url,*args,**kwargs)
        with patch.object(Session,'request',autospec=True,side_effect=rpc_only):
            result=APIClient().get(f'/api/verification/passport/{self.version.passport.public_reference}/').json()
            uploaded=APIClient().post('/api/verification/document/',{'file':SimpleUploadedFile('passport.pdf',self.pdf_bytes(),content_type='application/pdf')},format='multipart').json()
        self.assertTrue(result['blockchain']['historical_blockchain_authentic'])
        self.assertTrue(result['blockchain']['issuer_key_authorized'])
        self.assertNotIn('institutional_identity_verified',result['blockchain'])
        self.assertEqual(result['status'],'VALID')
        self.assertEqual(uploaded['status'],'VALID')

    def test_confirmed_proof_does_not_override_removed_issuer_trust(self):
        self.assertEqual(self.process(),'CONFIRMED')
        with override_settings(VERIFICATION_TRUSTED_ISSUER_REFERENCES=[]):
            result=APIClient().get(f'/api/verification/passport/{self.version.passport.public_reference}/').json()
        self.assertEqual(result['status'],'INVALID')
        self.assertFalse(result['blockchain']['blockchain_verified'])

    def test_independent_pdf_and_snapshot_recomputation_matches_actual_contract(self):
        self.assertEqual(self.process(),'CONFIRMED')
        proof=document_proof(self.document.public_reference)
        namespace=b'BTU_PASSPORT_POLYGON_V1\x00'+proof['chain_id'].to_bytes(32,'big')+bytes.fromhex(proof['contract_address'][2:])
        raw_hash=hashlib.sha256(self.pdf_bytes()).digest()
        expected=hashlib.sha256(namespace+b'PDF\x00'+b''.join(bytes.fromhex(proof[key]) for key in ['passport_key','version_key','document_key'])
                                +raw_hash+bytes.fromhex(proof['snapshot_sha256'])+bytes.fromhex(proof['commitment_salt'])).digest()
        record=self.gateway.contract.functions.commitments(bytes.fromhex(proof['document_key'])).call()
        self.assertEqual(record[2],expected)
        self.assertEqual(proof['snapshot_sha256'],self.version.content_sha256)

    def test_independent_transaction_cli_uses_no_institutional_database(self):
        self.assertEqual(self.process(),'CONFIRMED')
        proof=document_proof(self.document.public_reference)
        packet=Path(self.key_dir.name)/'public-proof.json'; packet.write_text(json.dumps(proof))
        root=Path(__file__).resolve().parents[3]
        result=subprocess.run([sys.executable,str(root/'blockchain/scripts/verify_transaction.py'),
            '--rpc-url',self.local.rpc_url,'--chain-id','31337','--registry-address',self.policy.contract_address,
            '--proof-json',str(packet),'--pdf',self.storage.path(self.document.storage_key),'--confirmations','1'],
            # Includes fresh interpreter/web3 startup on loaded CI machines;
            # individual provider requests retain their five-second timeout.
            capture_output=True,text=True,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(result.stdout)
        self.assertEqual(data['document_integrity'],'CONFIRMED')
        self.assertEqual(data['environment'],'LOCAL_ANVIL')
        self.assertEqual(data['institutional_current_status'],'NOT_CHECKED')
        self.assertNotIn('institutional_identity_verified',data)

    def test_migration_rollback_cannot_delete_confirmed_proof_history(self):
        self.assertEqual(self.process(),'CONFIRMED')
        from django.db.migrations.executor import MigrationExecutor
        executor=MigrationExecutor(connection)
        leaves=executor.loader.graph.leaf_nodes()
        try:
            with self.assertRaises(DatabaseError):
                executor.migrate([('passports','0006_snapshot_subcategory')])
        finally:
            MigrationExecutor(connection).migrate(leaves)
        self.assertEqual(PassportAnchor.objects.get(pk=self.anchor.pk).state,'CONFIRMED')


class PolicyTests(SimpleTestCase):
    def test_unconfigured_is_disabled(self):
        with override_settings(PASSPORT_BLOCKCHAIN_ENABLED=False):
            self.assertIsNone(load_policy())

    def test_mainnet_untrusted_local_host_and_plaintext_testnet_are_rejected(self):
        base = dict(PASSPORT_BLOCKCHAIN_ENABLED=True, PASSPORT_BLOCKCHAIN_CONTRACT_ADDRESS='0x'+'1'*40,
                    PASSPORT_BLOCKCHAIN_ISSUER_ADDRESS='0x'+'2'*40)
        for chain, url in [(1,'https://example.org'), (31337,'http://example.org'), (80002,'http://example.org')]:
            with override_settings(**base, PASSPORT_BLOCKCHAIN_CHAIN_ID=chain, PASSPORT_BLOCKCHAIN_RPC_URL=url):
                with self.assertRaises(ImproperlyConfigured):
                    load_policy()
