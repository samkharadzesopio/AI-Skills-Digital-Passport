"""Provider/transport unit checks plus actual Anvil/PostgreSQL recovery cases."""
from datetime import timedelta
from io import StringIO
import json
from unittest.mock import Mock, patch

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from web3 import Web3
from web3.providers import BaseProvider

from .chain import AnvilProvider, PolygonAmoyProvider, configured_gateway
from .models import PassportAnchor, ProofObservation, SignerNonce
from .policy import ChainPolicy
from .rpc import BoundedHTTPProvider, RPCUnavailable, RPCDeadlineExceeded, rpc_budget
from .services import _sign, document_proof, process_anchor, version_proof
from .tests import ChainDataMixin


class ProviderStabilizationTests(SimpleTestCase):
    def policy(self,chain=31337,url='http://127.0.0.1:8545'):
        return ChainPolicy(url,chain,'0x'+'1'*40,'0x'+'2'*40)

    def test_factory_selects_explicit_allowed_provider(self):
        self.assertIsInstance(configured_gateway(self.policy()),AnvilProvider)
        self.assertIsInstance(configured_gateway(self.policy(1337)),AnvilProvider)
        self.assertIsInstance(configured_gateway(self.policy(80002,'https://rpc.invalid')),PolygonAmoyProvider)
        for policy in (self.policy(137,'https://rpc.invalid'),self.policy(31337,'https://rpc.invalid'),self.policy(80002,'http://rpc.invalid')):
            with self.assertRaises(ImproperlyConfigured):
                configured_gateway(policy)

    def test_amoy_provider_accepts_poa_block_headers(self):
        class HeaderProvider(BaseProvider):
            def make_request(self,method,params):
                return {'jsonrpc':'2.0','id':1,'result':{'extraData':'0x'+'ab'*97}}
        gateway=PolygonAmoyProvider(self.policy(80002,'https://rpc.invalid'),Web3(HeaderProvider()))
        block=gateway.web3.eth.get_block('latest')
        self.assertEqual(bytes(block['proofOfAuthorityData']),bytes.fromhex('ab'*97))

    def response(self,status=200):
        response=Mock(status_code=status)
        context=Mock(); context.__enter__=Mock(return_value=response); context.__exit__=Mock(return_value=False)
        return context,response

    def test_slow_stream_exhausts_shared_deadline(self):
        provider=BoundedHTTPProvider('http://127.0.0.1:8545')
        context,response=self.response(); clock=[0.0]
        def slow_read(*args,**kwargs):
            clock[0]+=3
            return b'chunk'
        response.raw.read1.side_effect=slow_read
        with patch('apps.blockchain.rpc.time.monotonic',side_effect=lambda:clock[0]),patch.object(provider._session,'post',return_value=context):
            with rpc_budget(2),rpc_budget(25),self.assertRaises(RPCDeadlineExceeded):
                provider._make_request('eth_chainId',b'{}')

    def test_redirects_and_oversized_responses_are_rejected(self):
        provider=BoundedHTTPProvider('http://127.0.0.1:8545')
        context,response=self.response(302)
        with patch.object(provider._session,'post',return_value=context) as post,self.assertRaises(RPCUnavailable):
            provider._make_request('eth_chainId',b'{}')
        self.assertFalse(post.call_args.kwargs['allow_redirects'])
        context,response=self.response(); response.raw.read1.return_value=b'1234'
        provider.MAX_RESPONSE_BYTES=3
        with patch.object(provider._session,'post',return_value=context),self.assertRaises(RPCUnavailable):
            provider._make_request('eth_chainId',b'{}')

    def test_nested_budget_closes_rpc_connections_at_outer_exit(self):
        provider=BoundedHTTPProvider('http://127.0.0.1:8545')
        context,response=self.response(); response.raw.read1.side_effect=[b'{}',b'']
        with patch.object(provider._session,'post',return_value=context),patch.object(provider._session,'close') as close:
            with rpc_budget(6):
                with rpc_budget(25):
                    self.assertEqual(provider._make_request('eth_chainId',b'{}'),b'{}')
                close.assert_not_called()
            close.assert_called_once_with()

    def test_cleanup_error_does_not_leak_a_previous_request_deadline(self):
        provider=BoundedHTTPProvider('http://127.0.0.1:8545')
        context,response=self.response(); response.raw.read1.side_effect=[b'{}',b'',b'{}',b'']
        clock=[0.0]
        with patch('apps.blockchain.rpc.time.monotonic',side_effect=lambda:clock[0]),patch.object(provider._session,'post',return_value=context),patch.object(provider._session,'close',side_effect=OSError):
            with rpc_budget(1):
                self.assertEqual(provider._make_request('eth_chainId',b'{}'),b'{}')
            clock[0]=2
            with rpc_budget(1):
                self.assertEqual(provider._make_request('eth_chainId',b'{}'),b'{}')


class RecoveryStabilizationTests(ChainDataMixin,TransactionTestCase):
    def test_stuck_transaction_retains_signed_bytes_and_recovers_when_mined(self):
        self.local.rpc('evm_setAutomine',[False])
        try:
            self.assertEqual(process_anchor(self.anchor.pk),'SUBMITTED')
            self.anchor.refresh_from_db(); signed=bytes(self.anchor.signed_transaction)
            ProofObservation.objects.filter(operation=self.anchor,status='SIGNED').update(created_at=timezone.now()-timedelta(minutes=16))
            self.assertEqual(process_anchor(self.anchor.pk),'SUBMITTED')
            self.anchor.refresh_from_db()
            self.assertEqual(self.anchor.error_code,'STUCK_TRANSACTION_REVIEW_REQUIRED')
            proof=document_proof(self.document.public_reference)
            self.assertTrue(proof['operator_review_required'])
            self.assertEqual(proof['transaction_hash'],self.anchor.transaction_hash)
            self.assertFalse(proof['blockchain_verified'])
            self.assertEqual(bytes(self.anchor.signed_transaction),signed)
            self.assertEqual(SignerNonce.objects.get().next_nonce,self.anchor.nonce+1)
        finally:
            self.local.rpc('evm_setAutomine',[True]); self.local.mine_blocks(1)
        self.assertEqual(self.process(),'CONFIRMED')
        self.anchor.refresh_from_db(); self.assertEqual(bytes(self.anchor.signed_transaction),signed)

    def test_external_nonce_consumption_requires_review_without_resigning(self):
        row=_sign(self.anchor,self.gateway,self.signer)
        signed=bytes(row.signed_transaction)
        other=self.signer.sign_transaction({'chainId':31337,'nonce':row.nonce,'to':self.web3.eth.accounts[1],
            'value':1,'gas':21000,'gasPrice':self.web3.eth.gas_price})
        tx=self.web3.eth.send_raw_transaction(other.raw_transaction)
        self.web3.eth.wait_for_transaction_receipt(tx,timeout=5,poll_latency=.02)
        self.assertEqual(process_anchor(row.pk),'FAILED')
        row.refresh_from_db()
        self.assertEqual(row.error_code,'NONCE_CONSUMED_REVIEW_REQUIRED')
        self.assertFalse(row.retryable)
        self.assertEqual(bytes(row.signed_transaction),signed)
        self.assertEqual(process_anchor(row.pk),'FAILED')

    def test_rpc_deadline_does_not_trust_saved_confirmation(self):
        self.assertEqual(self.process(),'CONFIRMED')
        with patch('apps.blockchain.services.ChainGateway',return_value=self.gateway),patch.object(self.gateway,'verify',side_effect=RPCDeadlineExceeded):
            result=APIClient().get(f'/api/verification/passport/{self.version.passport.public_reference}/').json()
        self.assertEqual(result['status'],'UNVERIFIABLE')
        self.assertEqual(result['blockchain']['status'],'UNAVAILABLE')
        self.assertEqual(result['blockchain']['error'],'RPC_TIMEOUT')
        self.assertFalse(result['blockchain']['blockchain_verified'])
        self.assertEqual(PassportAnchor.objects.get(pk=self.anchor.pk).state,'CONFIRMED')

    def test_issuer_approval_is_separate_from_pending_chain_confirmation(self):
        pending=document_proof(self.document.public_reference)
        self.assertTrue(pending['institutional_issuer_approved'])
        self.assertFalse(pending['issuer_key_authorized'])
        self.assertFalse(pending['blockchain_verified'])
        self.assertTrue(pending['assessed_at'])
        self.assertEqual(self.process(),'CONFIRMED')
        confirmed=document_proof(self.document.public_reference)
        self.assertTrue(confirmed['institutional_issuer_approved'])
        self.assertTrue(confirmed['issuer_key_authorized'])
        self.assertTrue(confirmed['blockchain_verified'])

    def test_failed_operation_and_missing_configuration_are_not_public_pending(self):
        self.assertEqual(process_anchor(self.anchor.pk,signer=self.local.other_signer),'FAILED')
        public=APIClient().get(f'/api/verification/passport/{self.version.passport.public_reference}/').json()
        self.assertEqual(public['status'],'UNVERIFIABLE')
        self.assertEqual(public['blockchain']['status'],'FAILED')
        with override_settings(PASSPORT_BLOCKCHAIN_ENABLED=False):
            public=APIClient().get(f'/api/verification/passport/{self.version.passport.public_reference}/').json()
        self.assertEqual(public['status'],'UNVERIFIABLE')
        self.assertEqual(public['blockchain']['status'],'NOT_CONFIGURED')

    def test_operator_inspection_is_read_only_and_never_loads_a_signer(self):
        output=StringIO(); before=PassportAnchor.objects.get(pk=self.anchor.pk).updated_at
        with patch('apps.blockchain.services.load_signer',side_effect=AssertionError('No keys')):
            call_command('inspect_blockchain_operation',str(self.anchor.pk),stdout=output)
        result=json.loads(output.getvalue())
        self.assertEqual(result['state'],'PENDING')
        self.assertIsNone(result['nonce'])
        self.assertEqual(PassportAnchor.objects.get(pk=self.anchor.pk).updated_at,before)
        self.assertFalse(SignerNonce.objects.exists())

    def test_already_validated_document_has_zero_query_disabled_fast_path(self):
        with override_settings(PASSPORT_BLOCKCHAIN_ENABLED=False),self.assertNumQueries(0):
            proof=document_proof(self.document.public_reference,known_document=True)
        self.assertEqual(proof['status'],'NOT_CONFIGURED')
        self.assertIsNone(proof['assessed_at'])
        self.assertFalse(proof['blockchain_verified'])

    def test_invalid_version_configuration_is_not_assessed_or_sent_to_rpc(self):
        with override_settings(PASSPORT_BLOCKCHAIN_CHAIN_ID=137),self.assertNumQueries(0):
            proof=version_proof(self.version.pk)
        self.assertEqual(proof['status'],'NOT_CONFIGURED')
        self.assertEqual(proof['error'],'INVALID_DEPLOYMENT_POLICY')
        self.assertIsNone(proof['assessed_at'])
        self.assertFalse(proof['blockchain_verified'])
