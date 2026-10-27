"""Amoy/Anvil adapter validating actual chain code, receipts, events and lifecycle."""
import hashlib
import json
from typing import Protocol
from functools import lru_cache
from pathlib import Path
from hexbytes import HexBytes
from web3 import Web3
from web3.exceptions import TransactionNotFound
from web3.logs import DISCARD
from web3.middleware import ExtraDataToPOAMiddleware
from .policy import AMOY, LOCAL_CHAINS, validate_policy
from .rpc import BoundedHTTPProvider


@lru_cache(maxsize=1)
def artifact():
    return json.loads(Path(__file__).with_name('contract.json').read_text())


def hex_value(value):
    return '0x'+bytes(HexBytes(value)).hex()


class ProofError(Exception):
    def __init__(self,code,*,retryable=False):
        self.code,self.retryable=code,retryable
        super().__init__(code)


class ProofPending(ProofError):
    def __init__(self):
        super().__init__('AWAITING_CONFIRMATIONS',retryable=True)


class BlockchainProvider(Protocol):
    def validate_target(self): ...
    def signing_context(self): ...
    def unsigned_transaction(self,operation,nonce,gas_price): ...
    def broadcast(self,raw): ...
    def verify(self,operation): ...


class ChainGateway:
    def __init__(self,policy,web3=None):
        self.policy=policy
        self.web3=web3 or Web3(BoundedHTTPProvider(policy.rpc_url))
        if policy.chain_id == AMOY and 'passport_polygon_poa' not in self.web3.middleware_onion:
            self.web3.middleware_onion.inject(ExtraDataToPOAMiddleware, name='passport_polygon_poa', layer=0)
        self.contract=self.web3.eth.contract(address=Web3.to_checksum_address(policy.contract_address),abi=artifact()['abi'])

    def validate_target(self):
        from django.db import connection
        if connection.in_atomic_block:
            raise ProofError('RPC_INSIDE_DATABASE_TRANSACTION')
        if self.web3.eth.chain_id != self.policy.chain_id:
            raise ProofError('WRONG_CHAIN')
        actual=bytes(self.web3.eth.get_code(self.contract.address))
        expected=bytes.fromhex(artifact()['runtime_bytecode'][2:])
        if not actual or hashlib.sha256(actual).digest()!=hashlib.sha256(expected).digest():
            raise ProofError('UNAPPROVED_CONTRACT_CODE')

    def calldata(self,op):
        key=lambda value:bytes.fromhex(value)
        if op.operation_type=='ISSUE':
            return self.contract.encode_abi('anchorPassport',args=[key(op.passport_key),key(op.version_key),key(op.document_key),key(op.commitment)])
        if op.operation_type=='REPLACE':
            return self.contract.encode_abi('replacePassport',args=[key(op.passport_key),key(op.replacement_key)])
        if op.operation_type=='REVOKE':
            return self.contract.encode_abi('revokePassport',args=[key(op.passport_key)])
        raise ProofError('UNKNOWN_OPERATION')

    def signing_context(self):
        self.validate_target()
        if not self.contract.functions.hasRole(self.contract.functions.ISSUER_ROLE().call(),Web3.to_checksum_address(self.policy.issuer_address)).call():
            raise ProofError('UNAPPROVED_ISSUER_KEY')
        price=self.web3.eth.gas_price
        if not 0<price<=self.policy.max_gas_price_wei:
            raise ProofError('GAS_PRICE_LIMIT',retryable=True)
        return self.web3.eth.get_transaction_count(Web3.to_checksum_address(self.policy.issuer_address),'pending'),price

    def unsigned_transaction(self,op,nonce,gas_price):
        return {'chainId':self.policy.chain_id,'nonce':nonce,'to':self.contract.address,'gas':self.policy.gas_limit,
                'gasPrice':gas_price,'value':0,'data':self.calldata(op)}

    def broadcast(self,raw):
        return hex_value(self.web3.eth.send_raw_transaction(bytes(raw)))

    def submission_state(self,op):
        """Read only: avoid rebroadcasting mined/pool-known transactions."""
        self.validate_target()
        try:
            tx=self.web3.eth.get_transaction(op.transaction_hash)
        except TransactionNotFound:
            latest=self.web3.eth.get_transaction_count(Web3.to_checksum_address(op.issuer_address),'latest')
            if latest > op.nonce:
                raise ProofError('NONCE_CONSUMED_REVIEW_REQUIRED')
            return 'ABSENT'
        if hex_value(tx['hash']) != op.transaction_hash or tx['from'].lower() != op.issuer_address or tx['nonce'] != op.nonce:
            raise ProofError('TRANSACTION_OR_NONCE_MISMATCH')
        return 'MINED' if tx.get('blockNumber') is not None else 'PENDING'

    def verify(self,op):
        self.validate_target()
        try:
            receipt=self.web3.eth.get_transaction_receipt(op.transaction_hash)
        except TransactionNotFound:
            raise ProofPending() from None
        if receipt['status']!=1:
            raise ProofError('TRANSACTION_REVERTED')
        tx=self.web3.eth.get_transaction(op.transaction_hash)
        block=self.web3.eth.get_block(receipt['blockNumber'])
        confirmations=self.web3.eth.block_number-receipt['blockNumber']+1
        if (hex_value(receipt['transactionHash'])!=op.transaction_hash
            or hex_value(tx['hash'])!=op.transaction_hash
            or tx.get('chainId',self.policy.chain_id)!=self.policy.chain_id
            or (getattr(op,'nonce',None) is not None and tx['nonce']!=op.nonce)
            or tx['from'].lower()!=op.issuer_address or (tx.get('to') or '').lower()!=op.contract_address
            or tx.get('value',0)!=0 or bytes(HexBytes(tx['input']))!=bytes(HexBytes(self.calldata(op)))
            or receipt['blockHash']!=block['hash'] or tx['blockHash']!=receipt['blockHash']
            or op.transaction_hash not in [hex_value(value) for value in block['transactions']]):
            raise ProofError('TRANSACTION_OR_BLOCK_MISMATCH',retryable=True)
        key=lambda value:bytes.fromhex(value)
        state=self.contract.functions.passportState(key(op.passport_key)).call()
        if op.operation_type=='ISSUE':
            logs=self.contract.events.PassportAnchored().process_receipt(receipt,errors=DISCARD)
            expected=[key(op.document_key),key(op.passport_key),key(op.version_key),key(op.commitment),Web3.to_checksum_address(op.issuer_address)]
            match=[e for e in logs if e['address'].lower()==op.contract_address and [e['args'][k] for k in ('documentKey','passportKey','versionKey','digest','issuer')]==expected]
            stored=self.contract.functions.commitments(key(op.document_key)).call()
            if len(match)!=1 or list(stored)!=expected[1:]:
                raise ProofError('COMMITMENT_MISMATCH')
        elif op.operation_type=='REPLACE':
            logs=self.contract.events.PassportReplaced().process_receipt(receipt,errors=DISCARD)
            match=[e for e in logs if e['address'].lower()==op.contract_address and e['args']['previousKey']==key(op.passport_key) and e['args']['replacementKey']==key(op.replacement_key)]
            if len(match)!=1 or state!=2:
                raise ProofError('REPLACEMENT_MISMATCH')
        else:
            logs=self.contract.events.PassportRevoked().process_receipt(receipt,errors=DISCARD)
            match=[e for e in logs if e['address'].lower()==op.contract_address and e['args']['passportKey']==key(op.passport_key)]
            if len(match)!=1 or state!=3:
                raise ProofError('REVOCATION_MISMATCH')
        if confirmations<self.policy.confirmations:
            raise ProofPending()
        if self.web3.eth.get_block(receipt['blockNumber'])['hash']!=receipt['blockHash']:
            raise ProofError('BLOCK_REORGANIZED',retryable=True)
        return {'block_number':receipt['blockNumber'],'block_hash':hex_value(receipt['blockHash']),
                'confirmations':confirmations,'onchain_status':{0:'UNKNOWN',1:'ACTIVE',2:'REPLACED',3:'REVOKED'}[state]}


class PolygonAmoyProvider(ChainGateway):
    pass


class AnvilProvider(ChainGateway):
    pass


def configured_gateway(policy):
    validate_policy(policy)
    provider=AnvilProvider if policy.chain_id in LOCAL_CHAINS else PolygonAmoyProvider
    return provider(policy)
