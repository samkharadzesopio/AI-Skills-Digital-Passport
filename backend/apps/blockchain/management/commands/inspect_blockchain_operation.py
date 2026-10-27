"""Read-only operator diagnostics. Never loads a key, signs or broadcasts."""
import json
from django.core.management.base import BaseCommand, CommandError
from apps.blockchain.chain import configured_gateway, ProofError, ProofPending
from apps.blockchain.policy import load_policy
from apps.blockchain.rpc import rpc_budget, VERIFICATION_SECONDS
from apps.blockchain.services import _rows, _matches_policy


class Command(BaseCommand):
    help='Inspect a durable operation; optional --check-chain performs bounded read-only RPC.'

    def add_arguments(self,parser):
        parser.add_argument('operation_id')
        parser.add_argument('--check-chain',action='store_true')

    def handle(self,*args,**options):
        try:
            row=_rows().get(pk=options['operation_id'])
        except Exception:
            raise CommandError('Operation not found.') from None
        data={'operation_id':str(row.pk),'operation_type':row.operation_type,'state':row.state,
              'chain_id':row.chain_id,'transaction_hash':row.transaction_hash or None,'nonce':row.nonce,
              'error':row.error_code or None,'retryable':row.retryable,
              'operator_review_required':row.state=='FAILED' or row.error_code in ('STUCK_TRANSACTION_REVIEW_REQUIRED','NONCE_CONSUMED_REVIEW_REQUIRED','NONCE_CONFLICT_REVIEW_REQUIRED')}
        if options['check_chain']:
            try:
                with rpc_budget(VERIFICATION_SECONDS):
                    policy=load_policy()
                    if policy is None:
                        raise ProofError('NOT_CONFIGURED')
                    _matches_policy(row,policy)
                    gateway=configured_gateway(policy)
                    if not row.transaction_hash:
                        data['chain_status']='NOT_SIGNED'
                    else:
                        try:
                            data['receipt']=gateway.verify(row)
                            data['chain_status']='CONFIRMED'
                        except ProofPending:
                            data['chain_status']=gateway.submission_state(row)
            except ProofError as exc:
                data['chain_status']='UNVERIFIABLE'; data['chain_error']=exc.code
            except Exception:
                data['chain_status']='UNAVAILABLE'
        self.stdout.write(json.dumps(data,sort_keys=True))
