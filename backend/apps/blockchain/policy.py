"""Server-only deployment policy. Request input cannot select a chain or issuer."""
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from eth_account import Account
from web3 import Web3

LOCAL_CHAINS = {1337, 31337}
AMOY = 80002


@dataclass(frozen=True)
class ChainPolicy:
    rpc_url: str
    chain_id: int
    contract_address: str
    issuer_address: str
    confirmations: int = 3
    max_gas_price_wei: int = 50_000_000_000
    gas_limit: int = 250_000
    signing_key_file: str = ''
    issuer_identity_url: str = ''

    @property
    def environment(self):
        return 'LOCAL_ANVIL' if self.chain_id in LOCAL_CHAINS else 'POLYGON_AMOY'


def load_policy():
    if getattr(settings, 'PASSPORT_BLOCKCHAIN_ENABLED', False) is not True:
        return None
    try:
        policy = ChainPolicy(
            rpc_url=settings.PASSPORT_BLOCKCHAIN_RPC_URL,
            chain_id=int(settings.PASSPORT_BLOCKCHAIN_CHAIN_ID),
            contract_address=settings.PASSPORT_BLOCKCHAIN_CONTRACT_ADDRESS.lower(),
            issuer_address=settings.PASSPORT_BLOCKCHAIN_ISSUER_ADDRESS.lower(),
            confirmations=int(getattr(settings, 'PASSPORT_BLOCKCHAIN_CONFIRMATIONS', 3)),
            max_gas_price_wei=int(getattr(settings, 'PASSPORT_BLOCKCHAIN_MAX_GAS_PRICE_WEI', 50_000_000_000)),
            signing_key_file=getattr(settings, 'PASSPORT_BLOCKCHAIN_SIGNING_KEY_FILE', ''),
            issuer_identity_url=getattr(settings, 'PASSPORT_BLOCKCHAIN_ISSUER_IDENTITY_URL', ''),
        )
        parsed = urlsplit(policy.rpc_url)
        local = policy.chain_id in LOCAL_CHAINS
        if (policy.chain_id not in LOCAL_CHAINS | {AMOY}
            or parsed.username or parsed.password or parsed.fragment
            or not parsed.hostname
            or (local and (parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} or parsed.scheme not in {'http', 'https'}))
            or (not local and parsed.scheme != 'https')
            or not 1 <= policy.confirmations <= 64
            or not 1 <= policy.max_gas_price_wei <= 500_000_000_000
            or any(not Web3.is_address(address) or int(address, 16) == 0 for address in (policy.contract_address, policy.issuer_address))):
            raise ValueError
        return policy
    except (AttributeError, TypeError, ValueError):
        raise ImproperlyConfigured('Invalid Passport blockchain deployment policy.') from None


def load_signer(policy):
    try:
        path = Path(policy.signing_key_file)
        if not policy.signing_key_file or not path.is_file() or path.is_symlink() or path.stat().st_size > 256:
            raise ValueError
        # On Windows the operator must apply the equivalent restrictive file ACL.
        import os
        if os.name != 'nt' and path.stat().st_mode & 0o077:
            raise ValueError
        account = Account.from_key(path.read_text(encoding='ascii').strip())
        if account.address.lower() != policy.issuer_address:
            raise ValueError
        return account
    except (OSError, ValueError, UnicodeError):
        raise ImproperlyConfigured('A restricted signing-key file matching the approved issuer is required.') from None
