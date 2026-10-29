"""Read-only Amoy deployment plan. Never loads keys, signs or broadcasts."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from apps.blockchain.rpc import BoundedHTTPProvider, rpc_budget

CHAIN_ID = 80002
# Complete canonical artifact from the tested dc6da57 release; excludes checkout line endings.
TESTED_ARTIFACT_SHA256 = '91e22e19d6bff82a58456669356b642fcb9adce55493e3ea4f6327c9b57ab167'


class PreflightError(Exception):
    pass


def amoy_web3(rpc_url):
    web3 = Web3(BoundedHTTPProvider(rpc_url))
    # Match the runtime Amoy adapter: Polygon headers can exceed Ethereum's
    # 32-byte extraData limit. Normalization must run before Web3 validation.
    web3.middleware_onion.inject(ExtraDataToPOAMiddleware, name='passport_polygon_poa', layer=0)
    return web3


def address(value):
    if not Web3.is_address(value) or int(value, 16) == 0:
        raise PreflightError('INVALID_OR_ZERO_ROLE_ADDRESS')
    return Web3.to_checksum_address(value)


def checked_artifact():
    path = ROOT / 'backend/apps/blockchain/contract.json'
    artifact = json.loads(path.read_text())
    tested = json.loads((ROOT / 'blockchain/PHASE2_LOCAL_EVIDENCE.json').read_text())
    runtime = bytes.fromhex(artifact['runtime_bytecode'][2:])
    canonical_hash = hashlib.sha256(json.dumps(artifact, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if (canonical_hash != TESTED_ARTIFACT_SHA256 or hashlib.sha256(runtime).hexdigest() != tested['deployment']['runtime_sha256']
            or not artifact['compiler'].startswith('0.8.30+') or artifact['evmVersion'] != 'cancun'):
        raise PreflightError('ARTIFACT_DIFFERS_FROM_TESTED_RELEASE')
    return artifact, canonical_hash


def plan(web3, *, deployer, admin, issuer, max_gas_price_wei=50_000_000_000):
    deployer, admin, issuer = map(address, (deployer, admin, issuer))
    if type(max_gas_price_wei) is not int or not 1 <= max_gas_price_wei <= 500_000_000_000:
        raise PreflightError('INVALID_FEE_CEILING')
    if web3.eth.chain_id != CHAIN_ID:
        raise PreflightError('WRONG_CHAIN_NO_FALLBACK')
    artifact, artifact_hash = checked_artifact()
    for account in (deployer, issuer):
        if web3.eth.get_code(account):
            raise PreflightError('DEDICATED_EOA_REQUIRED')
    pending = web3.eth.get_transaction_count(deployer, 'pending')
    latest_nonce = web3.eth.get_transaction_count(deployer, 'latest')
    if pending != latest_nonce:
        raise PreflightError('PENDING_DEPLOYER_TRANSACTIONS_REVIEW_REQUIRED')
    block = web3.eth.get_block('latest')
    price = web3.eth.gas_price
    if type(price) is not int or not 0 < price <= max_gas_price_wei:
        raise PreflightError('GAS_PRICE_OUTSIDE_APPROVED_CEILING')
    constructor = web3.eth.contract(abi=artifact['abi'], bytecode=artifact['bytecode']).constructor(admin, issuer)
    tx = {'from': deployer, 'chainId': CHAIN_ID, 'nonce': pending, 'value': 0,
          'data': constructor.data_in_transaction}
    estimate = web3.eth.estimate_gas(tx)
    gas = (estimate * 120 + 99) // 100
    if gas >= block['gasLimit']:
        raise PreflightError('DEPLOYMENT_EXCEEDS_BLOCK_GAS_LIMIT')
    tx['gas'] = gas
    tx['gasPrice'] = price
    balance = web3.eth.get_balance(deployer)
    if web3.eth.chain_id != CHAIN_ID or web3.eth.get_block(block['number'])['hash'] != block['hash']:
        raise PreflightError('CHAIN_CHANGED_DURING_PREFLIGHT')
    if (web3.eth.get_transaction_count(deployer, 'pending') != pending
            or web3.eth.get_transaction_count(deployer, 'latest') != latest_nonce):
        raise PreflightError('DEPLOYER_NONCE_CHANGED_DURING_PREFLIGHT')
    # Reserve is conservative per-operation worker gas, not a fabricated live
    # estimate of unknown future Passport calldata. It is never spending approval.
    reserve = 3 * 250_000 * price
    cost = gas * price
    return {
        'status': 'PREFLIGHT_PASSED_APPROVAL_REQUIRED' if balance >= cost else 'INSUFFICIENT_DEPLOYMENT_BALANCE',
        'chain_id': CHAIN_ID, 'network': 'Polygon Amoy',
        'deployer': deployer, 'constructor': {'admin': admin, 'issuer': issuer},
        'separate_admin_and_issuer': admin != issuer,
        'artifact_sha256': artifact_hash,
        'runtime_sha256': hashlib.sha256(bytes.fromhex(artifact['runtime_bytecode'][2:])).hexdigest(),
        'creation_bytecode_sha256': hashlib.sha256(bytes.fromhex(artifact['bytecode'][2:])).hexdigest(),
        'observed_block': block['number'], 'observed_block_hash': Web3.to_hex(block['hash']),
        'observed_nonce': pending, 'balance_wei': balance, 'gas_estimate': estimate,
        'gas_limit_with_20_percent_buffer': gas, 'legacy_gas_price_wei': price,
        'max_allowed_gas_price_wei': max_gas_price_wei,
        'deployment_max_cost_at_quote_wei': cost,
        'balance_covers_deployment_at_quote': balance >= cost,
        'three_later_operations_conservative_reserve_wei': reserve,
        'balance_covers_deployment_and_reserve': balance >= cost + reserve,
        'later_operations': ['ISSUE', 'REPLACE', 'ISSUE_NEW_IDENTITY'],
        'later_operations_need_separate_approval': True,
        'required_confirmations': 3, 'signing_custody_verified': False,
        'approval_granted': False, 'transactions_broadcast': 0,
        'unsigned_transaction': tx,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deployer', required=True)
    parser.add_argument('--admin', required=True)
    parser.add_argument('--issuer', required=True)
    parser.add_argument('--max-gas-price-wei', type=int, default=50_000_000_000)
    parser.add_argument('--output', help='New private report path outside the checkout; refuses overwrite.')
    args = parser.parse_args()
    try:
        rpc = os.environ.get('AMOY_RPC_URL', '')
        parsed = urlsplit(rpc)
        parsed.port
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
                or parsed.password or parsed.fragment):
            raise PreflightError('CONFIGURE_HTTPS_AMOY_RPC_URL_SECURELY')
        output = Path(args.output).expanduser().resolve() if args.output else None
        if output and (output == ROOT or ROOT in output.parents):
            raise PreflightError('REPORT_MUST_BE_OUTSIDE_CHECKOUT')
        with rpc_budget(25):
            report = plan(amoy_web3(rpc), deployer=args.deployer, admin=args.admin,
                          issuer=args.issuer, max_gas_price_wei=args.max_gas_price_wei)
        if output:
            fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(report, stream, indent=2)
                stream.write('\n')
        summary = {key: value for key, value in report.items() if key != 'unsigned_transaction'}
        print(json.dumps(summary, indent=2))
        return 0 if report['balance_covers_deployment_at_quote'] else 2
    except PreflightError as error:
        print(json.dumps({'status': 'BLOCKED', 'code': str(error), 'transactions_broadcast': 0}))
    except Exception:
        # Provider errors may contain credential-bearing URLs. Never echo them.
        print(json.dumps({'status': 'BLOCKED', 'code': 'PREFLIGHT_OR_REPORT_UNAVAILABLE', 'transactions_broadcast': 0}))
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
