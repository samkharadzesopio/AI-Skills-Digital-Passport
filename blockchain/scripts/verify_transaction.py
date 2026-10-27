"""Read-only independent chain/PDF verification: no institutional database or key."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from django.conf import settings
if not settings.configured:
    settings.configure(USE_TZ=True,DATABASES={'default':{'ENGINE':'django.db.backends.dummy'}})
from apps.blockchain.chain import configured_gateway, ProofError, ProofPending
from apps.blockchain.commitments import pdf_commitment
from apps.blockchain.policy import ChainPolicy, AMOY, LOCAL_CHAINS
from apps.blockchain.rpc import rpc_budget, VERIFICATION_SECONDS, RPCDeadlineExceeded


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rpc-url',required=True)
    parser.add_argument('--chain-id',type=int,default=80002)
    parser.add_argument('--registry-address',required=True)
    parser.add_argument('--proof-json',required=True)
    parser.add_argument('--pdf',required=True)
    parser.add_argument('--confirmations',type=int,default=3)
    args=parser.parse_args()
    parsed=urlsplit(args.rpc_url)
    if args.chain_id not in LOCAL_CHAINS | {AMOY} or (args.chain_id==AMOY and parsed.scheme!='https') or (args.chain_id in LOCAL_CHAINS and parsed.hostname not in ('localhost','127.0.0.1','::1')):
        parser.error('Only HTTPS Polygon Amoy or loopback Anvil verification is supported.')
    if not 1<=args.confirmations<=64:
        parser.error('Confirmations must be between 1 and 64.')
    pdf=Path(args.pdf); packet=Path(args.proof_json)
    if pdf.stat().st_size>5*1024*1024 or packet.stat().st_size>65536:
        parser.error('Input exceeds the verification limit.')
    data=json.loads(packet.read_text())
    result={'document_integrity':'UNVERIFIABLE',
            'institutional_issuer_approved':None,
            'institutional_current_status':'NOT_CHECKED','source':'INDEPENDENT_EVM_PDF_CHECK',
            'chain_id':args.chain_id,'registry_address':args.registry_address.lower(),
            'environment':'LOCAL_ANVIL' if args.chain_id in LOCAL_CHAINS else 'POLYGON_AMOY'}
    try:
        policy=ChainPolicy(args.rpc_url,args.chain_id,args.registry_address.lower(),data['issuer_address'].lower(),
                           confirmations=args.confirmations)
        gateway=configured_gateway(policy)
        actual=hashlib.sha256(pdf.read_bytes()).hexdigest()
        digest=pdf_commitment(policy,data['passport_key'],data['version_key'],data['document_key'],actual,data['snapshot_sha256'],data['commitment_salt'])
        if actual!=data['pdf_sha256'] or digest!=data['commitment']:
            raise ProofError('PDF_OR_SNAPSHOT_COMMITMENT_MISMATCH')
        operation=SimpleNamespace(**{key:data[key] for key in ('passport_key','version_key','document_key','commitment','transaction_hash','issuer_address')},
                                  operation_type='ISSUE',contract_address=policy.contract_address)
        proof=gateway.verify(operation)
        if data.get('replacement_transaction_hash'):
            tx=gateway.web3.eth.get_transaction(data['replacement_transaction_hash'])
            fn,params=gateway.contract.decode_function_input(tx['input'])
            if fn.fn_name!='replacePassport' or bytes(params['passportKey']).hex()!=data['passport_key']:
                raise ProofError('REPLACEMENT_DEPENDENCY_MISMATCH')
            dependency=SimpleNamespace(operation_type='REPLACE',passport_key=bytes(params['previousKey']).hex(),
                replacement_key=bytes(params['passportKey']).hex(),transaction_hash=data['replacement_transaction_hash'],
                issuer_address=tx['from'].lower(),contract_address=policy.contract_address)
            gateway.verify(dependency)
        result.update(proof,document_integrity='CONFIRMED',transaction_hash=operation.transaction_hash)
    except ProofPending:
        result['document_integrity']='PENDING_BLOCKCHAIN'
    except ProofError as error:
        result['error']=error.code
    except RPCDeadlineExceeded:
        result['error']='RPC_TIMEOUT'
    except Exception:
        result['error']='EVIDENCE_OR_RPC_UNAVAILABLE'
    print(json.dumps(result,sort_keys=True))
    return 0 if result['document_integrity']=='CONFIRMED' else 1


if __name__=='__main__':
    with rpc_budget(VERIFICATION_SECONDS):
        raise SystemExit(main())
