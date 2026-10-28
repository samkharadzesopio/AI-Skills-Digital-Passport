"""Amoy-numbered local EVM rehearsal; never connects to Polygon or spends POL.

The real Anvil transport is injected into the Amoy adapter. HTTPS/PoA policy is
covered separately; this is not a public Amoy deployment or RPC acceptance.
"""
import hashlib
from dataclasses import replace
from types import SimpleNamespace

from django.test import SimpleTestCase

from .anvil_testing import AnvilChain
from .chain import PolygonAmoyProvider, ProofError, ProofPending, artifact, hex_value
from .policy import ChainPolicy


class AmoyEnvelopeTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.local = AnvilChain(chain_id=80002)
        cls.addClassCleanup(cls.local.close)
        cls.web3 = cls.local.web3
        cls.signer = cls.local.signer
        factory = cls.web3.eth.contract(abi=artifact()['abi'], bytecode=artifact()['bytecode'])
        receipt = cls.web3.eth.wait_for_transaction_receipt(
            factory.constructor(cls.web3.eth.accounts[1], cls.signer.address).transact(
                {'from': cls.web3.eth.accounts[1]}), timeout=10, poll_latency=.02)
        cls.policy = ChainPolicy(
            'https://amoy.fixture.invalid', 80002, receipt.contractAddress.lower(),
            cls.signer.address.lower(), confirmations=3)

    def setUp(self):
        super().setUp()
        snapshot = self.local.take_snapshot()
        self.addCleanup(self.local.revert_to_snapshot, snapshot)
        self.gateway = PolygonAmoyProvider(self.policy, self.web3)
        digest = lambda value: hashlib.sha256(value).hexdigest()
        self.operation = SimpleNamespace(
            operation_type='ISSUE', passport_key=digest(b'synthetic passport'),
            version_key=digest(b'synthetic version'), document_key=digest(b'synthetic PDF'),
            commitment=digest(b'synthetic commitment'), contract_address=self.policy.contract_address,
            issuer_address=self.policy.issuer_address)

    def submit(self):
        nonce, price = self.gateway.signing_context()
        unsigned = self.gateway.unsigned_transaction(self.operation, nonce, price)
        estimate = self.web3.eth.estimate_gas({**unsigned, 'from': self.signer.address})
        self.assertLessEqual(estimate, self.policy.gas_limit)
        signed = self.signer.sign_transaction(unsigned)
        self.operation.signed_transaction = bytes(signed.raw_transaction)
        self.operation.transaction_hash = hex_value(signed.hash)
        self.operation.nonce = nonce
        self.gateway.validate_signed(self.operation)
        self.assertEqual(self.gateway.broadcast(signed.raw_transaction), self.operation.transaction_hash)
        return self.web3.eth.wait_for_transaction_receipt(signed.hash, timeout=10, poll_latency=.02)

    def test_legacy_eip155_envelope_confirms_on_eip1559_chain_80002(self):
        receipt = self.submit()
        self.assertEqual(receipt['status'], 1)
        self.assertLessEqual(receipt['gasUsed'], self.policy.gas_limit)
        tx = self.web3.eth.get_transaction(receipt['transactionHash'])
        self.assertEqual(tx['chainId'], 80002)
        self.assertEqual(tx['type'], 0)
        self.assertIn(tx['v'], (2 * 80002 + 35, 2 * 80002 + 36))
        self.assertGreater(self.web3.eth.get_block(receipt['blockNumber'])['baseFeePerGas'], 0)
        self.local.mine_blocks(2)
        proof = self.gateway.verify(self.operation)
        self.assertGreaterEqual(proof['confirmations'], 3)
        self.assertEqual(proof['onchain_status'], 'ACTIVE')

    def test_three_confirmations_are_required_on_chain_80002(self):
        self.submit()
        with self.assertRaises(ProofPending):
            self.gateway.verify(self.operation)
        self.local.mine_blocks(2)
        self.assertEqual(self.gateway.verify(self.operation)['confirmations'], 3)

    def test_wrong_chain_refused_before_submission(self):
        gateway = PolygonAmoyProvider(replace(self.policy, chain_id=31337), self.web3)
        before = self.web3.eth.get_transaction_count(self.signer.address)
        with self.assertRaisesRegex(ProofError, 'WRONG_CHAIN'):
            gateway.signing_context()
        self.assertEqual(self.web3.eth.get_transaction_count(self.signer.address), before)

    def test_fee_ceiling_refused_without_consuming_nonce(self):
        gateway = PolygonAmoyProvider(replace(self.policy, max_gas_price_wei=1), self.web3)
        before = self.web3.eth.get_transaction_count(self.signer.address)
        with self.assertRaisesRegex(ProofError, 'GAS_PRICE_LIMIT'):
            gateway.signing_context()
        self.assertEqual(self.web3.eth.get_transaction_count(self.signer.address), before)

    def test_signed_payload_cannot_be_replayed_with_other_chain_policy(self):
        self.submit()
        gateway = PolygonAmoyProvider(replace(self.policy, chain_id=31337), self.web3)
        with self.assertRaisesRegex(ProofError, 'SIGNED_TRANSACTION_REVIEW_REQUIRED'):
            gateway.validate_signed(self.operation)
