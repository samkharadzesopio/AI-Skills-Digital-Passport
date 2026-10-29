"""Guard tests and real disposable chain-80002 rehearsal; no public transactions."""
import unittest
import contextlib
import io
import json
import os
import tempfile
from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import amoy_preflight as preflight
from apps.blockchain.anvil_testing import AnvilChain
from web3.providers import BaseProvider


class PreflightTests(unittest.TestCase):
    def test_polygon_headers_are_normalized_before_validation(self):
        class HeaderProvider(BaseProvider):
            def make_request(self, method, params):
                return {'jsonrpc': '2.0', 'id': 1, 'result': {'extraData': '0x' + 'ab' * 97}}
        with patch.object(preflight, 'BoundedHTTPProvider', return_value=HeaderProvider()):
            block = preflight.amoy_web3('https://synthetic.invalid').eth.get_block('latest')
        self.assertEqual(bytes(block['proofOfAuthorityData']), bytes.fromhex('ab' * 97))

    def invoke(self, *args):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['amoy_preflight.py', '--deployer', '0x'+'1'*40,
                                        '--admin', '0x'+'2'*40, '--issuer', '0x'+'3'*40, *args]):
            with contextlib.redirect_stdout(output):
                code = preflight.main()
        return code, json.loads(output.getvalue())

    def test_cli_rejects_non_https_without_contacting_rpc(self):
        with patch.dict(os.environ, {'AMOY_RPC_URL': 'http://synthetic.invalid'}):
            with patch.object(preflight, 'amoy_web3', side_effect=AssertionError('No RPC')):
                code, output = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(output['code'], 'CONFIGURE_HTTPS_AMOY_RPC_URL_SECURELY')

    def test_cli_never_echoes_credential_bearing_provider_errors(self):
        private_url = 'https://synthetic.invalid/PRIVATE_TEST_TOKEN'
        with patch.dict(os.environ, {'AMOY_RPC_URL': private_url}):
            with patch.object(preflight, 'amoy_web3', side_effect=ConnectionError(private_url)):
                code, output = self.invoke()
        self.assertEqual(code, 1)
        self.assertEqual(output['transactions_broadcast'], 0)
        self.assertNotIn('PRIVATE_TEST_TOKEN', json.dumps(output))

    def test_report_refuses_checkout_and_existing_files(self):
        with patch.dict(os.environ, {'AMOY_RPC_URL': 'https://synthetic.invalid'}):
            with patch.object(preflight, 'amoy_web3', side_effect=AssertionError('No RPC')):
                code, output = self.invoke('--output', str(preflight.ROOT / 'unsafe-report.json'))
            self.assertEqual(code, 1)
            self.assertEqual(output['code'], 'REPORT_MUST_BE_OUTSIDE_CHECKOUT')
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'report.json'
                path.write_text('preserve')
                with patch.object(preflight, 'amoy_web3'), patch.object(preflight, 'plan', return_value={}):
                    code, _ = self.invoke('--output', str(path))
                self.assertEqual(code, 1)
                self.assertEqual(path.read_text(), 'preserve')

    def test_mainnet_rejected_before_other_rpc_reads(self):
        rpc = SimpleNamespace(eth=SimpleNamespace(chain_id=137))
        with self.assertRaisesRegex(preflight.PreflightError, 'WRONG_CHAIN'):
            preflight.plan(rpc, deployer='0x'+'1'*40, admin='0x'+'2'*40, issuer='0x'+'3'*40)

    def test_zero_roles_rejected(self):
        with self.assertRaisesRegex(preflight.PreflightError, 'INVALID_OR_ZERO_ROLE'):
            preflight.plan(None, deployer='0x'+'0'*40, admin='0x'+'2'*40, issuer='0x'+'3'*40)

    def test_changed_artifact_rejected(self):
        with patch.object(preflight, 'TESTED_ARTIFACT_SHA256', '0'*64):
            with self.assertRaisesRegex(preflight.PreflightError, 'ARTIFACT_DIFFERS'):
                preflight.checked_artifact()

    def test_actual_local_plan_balance_fee_guards_and_deployment(self):
        node = AnvilChain(chain_id=80002)
        try:
            rpc = node.web3
            deployer = rpc.eth.accounts[1]
            admin = rpc.eth.accounts[2]
            issuer = node.signer.address
            before = rpc.eth.get_transaction_count(deployer)
            block = rpc.eth.block_number
            plan = preflight.plan(rpc, deployer=deployer, admin=admin, issuer=issuer)
            self.assertEqual(rpc.eth.block_number, block)
            self.assertEqual(rpc.eth.get_transaction_count(deployer), before)
            self.assertEqual(plan['transactions_broadcast'], 0)
            self.assertFalse(plan['approval_granted'])
            self.assertTrue(plan['balance_covers_deployment_and_reserve'])
            with self.assertRaisesRegex(preflight.PreflightError, 'GAS_PRICE_OUTSIDE'):
                preflight.plan(rpc, deployer=deployer, admin=admin, issuer=issuer, max_gas_price_wei=1)
            with patch.object(rpc.eth, 'get_transaction_count', side_effect=[before, before, before + 1]):
                with self.assertRaisesRegex(preflight.PreflightError, 'DEPLOYER_NONCE_CHANGED'):
                    preflight.plan(rpc, deployer=deployer, admin=admin, issuer=issuer)
            node.rpc('anvil_setBalance', [deployer, '0x0'])
            insufficient = preflight.plan(rpc, deployer=deployer, admin=admin, issuer=issuer)
            node.rpc('anvil_setBalance', [deployer, hex(10**22)])
            self.assertEqual(insufficient['status'], 'INSUFFICIENT_DEPLOYMENT_BALANCE')
            # Broadcast ONLY on this owned disposable Anvil node. The production
            # preflight has no signing/broadcast method or --broadcast argument.
            receipt = rpc.eth.wait_for_transaction_receipt(
                rpc.eth.send_transaction(plan['unsigned_transaction']), timeout=10, poll_latency=.02)
            self.assertEqual(receipt['status'], 1)
            node.mine_blocks(2)
            a, _ = preflight.checked_artifact()
            self.assertEqual(bytes(rpc.eth.get_code(receipt.contractAddress)), bytes.fromhex(a['runtime_bytecode'][2:]))
            contract = rpc.eth.contract(address=receipt.contractAddress, abi=a['abi'])
            self.assertEqual(contract.functions.defaultAdmin().call(), admin)
            self.assertTrue(contract.functions.hasRole(contract.functions.ISSUER_ROLE().call(), issuer).call())
        finally:
            node.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
