"""Public network labels and links; never use request/provider-supplied URLs."""
import re

from .policy import AMOY, LOCAL_CHAINS


def network_metadata(chain_id=None, transaction_hash=None):
    network = 'Polygon Amoy' if chain_id == AMOY else 'Anvil' if chain_id in LOCAL_CHAINS else None
    explorer = None
    if (chain_id == AMOY and isinstance(transaction_hash, str)
            and re.fullmatch(r'0x[0-9a-fA-F]{64}', transaction_hash)):
        explorer = 'https://amoy.polygonscan.com/tx/' + transaction_hash
    return {'network': network, 'transaction_explorer_url': explorer}
