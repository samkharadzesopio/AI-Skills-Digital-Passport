"""Prepare a PUBLIC, unsigned registry declaration for approval/publication by BTU."""
import argparse
import hashlib
import json
from datetime import datetime,timezone
from pathlib import Path
from web3 import Web3


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--registry-address',required=True)
    parser.add_argument('--expires-at',required=True,help='Future ISO-8601 timestamp with time zone')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if not Web3.is_address(args.registry_address) or int(args.registry_address,16)==0:
        parser.error('Supply the actual deployed Polygon Amoy registry address.')
    try:
        expires=datetime.fromisoformat(args.expires_at.replace('Z','+00:00'))
        if expires.tzinfo is None or expires<=datetime.now(timezone.utc):
            raise ValueError
    except ValueError:
        parser.error('Expiry must be a future, time-zone-aware ISO timestamp.')
    output=Path(args.output)
    if output.exists():
        parser.error('The output already exists; use a new review file.')
    artifact=Path(__file__).resolve().parents[2]/'backend/apps/blockchain/contract.json'
    data=json.loads(artifact.read_text())
    statement={'issuer_reference':'BTU-UNIVERSITY','chain_id':80002,
        'registry_address':args.registry_address.lower(),
        'runtime_sha256':hashlib.sha256(bytes.fromhex(data['runtime_bytecode'][2:])).hexdigest(),
        'published_at':datetime.now(timezone.utc).isoformat(),'expires_at':expires.isoformat()}
    output.write_text(json.dumps(statement,indent=2)+'\n')
    print('Prepared PUBLIC declaration. It establishes no authority until BTU approves and publishes it on its HTTPS domain.')


if __name__=='__main__':
    main()
