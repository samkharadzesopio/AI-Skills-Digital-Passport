"""Durable PDF proof queue. Network IO is always outside database transactions."""
import hashlib
import secrets
from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured
from django.db import connection, transaction
from django.db.models import Q, F, Exists, OuterRef, Value, Case, When, CharField
from django.db.models.functions import Cast, Concat
from django.utils import timezone

from apps.credentials.models import BTU_ISSUER_REFERENCE, CredentialIssuer
from apps.passports.models import PassportDocument, DigitalPassport, PassportLifecycleEvent
from apps.verification.records import trusted_issuer
from .chain import configured_gateway as ChainGateway, ProofError, ProofPending, hex_value
from .models import PassportAnchor, SignerNonce, ProofObservation
from .commitments import passport_key, document_material
from .policy import load_policy, load_signer
from .rpc import rpc_budget, VERIFICATION_SECONDS, WORKER_SECONDS, RPCUnavailable, RPCDeadlineExceeded

MAX_FAILURES = 10
STUCK_AFTER_SECONDS = 900


def _issuer():
    issuer = CredentialIssuer.objects.filter(reference=BTU_ISSUER_REFERENCE).first()
    if issuer is None or not trusted_issuer(issuer.reference, issuer.reference, issuer.is_trusted):
        raise ProofError('BTU_ISSUER_NOT_APPROVED')
    return issuer


def _target(policy, passport):
    return {'passport':passport,'issuer':_issuer(),'chain_id':policy.chain_id,
            'contract_address':policy.contract_address,'issuer_address':policy.issuer_address,
            'passport_key':passport_key(passport,policy)}


def enqueue_document(document):
    policy=load_policy()
    if policy is None:
        return None
    if document.status!='ISSUED' or document.passport_version.status!='ISSUED':
        raise ProofError('DOCUMENT_NOT_ISSUED')
    passport=document.passport_version.passport
    with transaction.atomic():
        passport=DigitalPassport.objects.select_for_update().get(pk=passport.pk)
        if passport.status!='ACTIVE':
            return None
        dependency=PassportAnchor.objects.filter(replacement=passport,operation_type='REPLACE').first()
        if dependency is None and passport.replaces_id:
            event=PassportLifecycleEvent.objects.get(replacement=passport,event_type='NAME_CHANGE')
            dependency=enqueue_replacement(event.previous,passport,event)
        values={**_target(policy,passport),**document_material(document,policy,secrets.token_hex(32)),
                'operation_type':'ISSUE','operation_key':f'document:{document.public_reference}',
                'pdf_sha256':document.pdf_sha256,'depends_on':dependency}
        row,_=PassportAnchor.objects.get_or_create(document=document,defaults=values)
        return row


def enqueue_replacement(previous,replacement,event):
    policy=load_policy()
    if policy is None:
        return None  # The immutable registrar event remains the durable intent.
    row,_=PassportAnchor.objects.get_or_create(operation_key=f'replacement:{event.pk}',defaults={
        **_target(policy,previous),'replacement':replacement,'operation_type':'REPLACE',
        'replacement_key':passport_key(replacement,policy)})
    return row


def enqueue_revocation(passport,event):
    policy=load_policy()
    if policy is None:
        return None
    row,_=PassportAnchor.objects.get_or_create(operation_key=f'revocation:{event.pk}',defaults={
        **_target(policy,passport),'operation_type':'REVOKE'})
    return row


def _matches_policy(anchor,policy):
    if (anchor.chain_id!=policy.chain_id or anchor.contract_address!=policy.contract_address
        or anchor.issuer_id!=_issuer().pk or anchor.passport_key!=passport_key(anchor.passport,policy)):
        raise ProofError('ANCHOR_TARGET_NOT_APPROVED')
    if anchor.operation_type=='ISSUE':
        expected=document_material(anchor.document,policy,anchor.commitment_salt)
        if (anchor.pdf_sha256!=anchor.document.pdf_sha256 or anchor.document.status!='ISSUED'
            or any(getattr(anchor,key)!=value for key,value in expected.items())):
            raise ProofError('DOCUMENT_COMMITMENT_MISMATCH')
    elif anchor.operation_type=='REPLACE' and anchor.replacement_key!=passport_key(anchor.replacement,policy):
        raise ProofError('REPLACEMENT_TARGET_MISMATCH')


def _assert_stored_pdf(anchor):
    # Pin the actual bytes before spending gas. The existing service owns storage paths.
    from apps.passports.document_services import open_passport_document_for_student
    document, stream = open_passport_document_for_student(
        document_reference=anchor.document.public_reference,
        student_id=anchor.document.passport_version.passport.student_id,
    )
    digest, size, header = hashlib.sha256(), 0, b''
    try:
        for chunk in iter(lambda: stream.read(65536), b''):
            size += len(chunk)
            if size > 5 * 1024 * 1024:
                raise ProofError('PDF_STORAGE_MISMATCH')
            header = (header + chunk)[:5]
            digest.update(chunk)
    finally:
        stream.close()
    if size != document.byte_size or digest.hexdigest() != anchor.pdf_sha256 or header != b'%PDF-':
        raise ProofError('PDF_STORAGE_MISMATCH')


def _rows():
    return PassportAnchor.objects.select_related('issuer','passport','replacement','depends_on','document__passport_version__passport')


def _sign(anchor, gateway, signer):
    network_nonce, gas_price = gateway.signing_context()
    with transaction.atomic():
        row = _rows().select_for_update(of=('self',)).get(pk=anchor.pk)
        if row.signed_transaction is not None:
            return row
        if row.operation_type=='ISSUE' and row.passport.status!='ACTIVE':
            raise ProofError('CANCELLED_BEFORE_ANCHORING')
        nonce_key = f'{row.chain_id}:{row.issuer_address}'
        SignerNonce.objects.get_or_create(key=nonce_key)
        counter = SignerNonce.objects.select_for_update().get(pk=nonce_key)
        nonce = max(network_nonce, counter.next_nonce)
        signed = signer.sign_transaction(gateway.unsigned_transaction(row, nonce, gas_price))
        row.signed_transaction = bytes(signed.raw_transaction)
        row.transaction_hash, row.nonce = hex_value(signed.hash), nonce
        row.state = PassportAnchor.State.SIGNED
        row.save(update_fields=['signed_transaction', 'transaction_hash', 'nonce', 'state', 'updated_at'])
        counter.next_nonce = nonce + 1
        counter.save(update_fields=['next_nonce'])
        ProofObservation.objects.create(operation=row,status='SIGNED')
        return row


def _record(anchor_id, *, proof=None, error=None, pending=False):
    with transaction.atomic():
        row = PassportAnchor.objects.select_for_update().get(pk=anchor_id)
        if row.state == PassportAnchor.State.CONFIRMED:
            return row.state
        if proof is not None:
            row.state, row.block_number, row.block_hash = 'CONFIRMED', proof['block_number'], proof['block_hash']
            row.error_code, row.next_attempt_at = '', None
        elif pending:
            row.state, row.error_code = 'SUBMITTED', 'AWAITING_CONFIRMATIONS'
            signed_at=row.observations.filter(status='SIGNED').order_by('created_at').values_list('created_at',flat=True).first() or row.created_at
            if (timezone.now()-signed_at).total_seconds() >= STUCK_AFTER_SECONDS:
                row.error_code='STUCK_TRANSACTION_REVIEW_REQUIRED'
            row.next_attempt_at = timezone.now() + timedelta(seconds=15)
        else:
            row.attempts += 1
            row.error_code, row.retryable = error.code, error.retryable
            row.state = ('SIGNED' if row.signed_transaction else 'PENDING') if error.retryable and row.attempts < MAX_FAILURES else 'FAILED'
            row.next_attempt_at = timezone.now() + timedelta(seconds=min(300, 5 * 2 ** min(row.attempts, 6)))
        row.save()
        return row.state


def process_anchor(anchor_id, *, gateway=None, signer=None):
    with rpc_budget(WORKER_SECONDS):
        return _process_anchor(anchor_id,gateway=gateway,signer=signer)


def _process_anchor(anchor_id, *, gateway=None, signer=None):
    if connection.vendor != 'postgresql' or connection.in_atomic_block:
        raise ImproperlyConfigured('Proof processing requires PostgreSQL and no enclosing transaction.')
    policy = load_policy()
    if policy is None:
        return 'DISABLED'
    anchor = _rows().get(pk=anchor_id)
    if anchor.state in ('CONFIRMED', 'FAILED'):
        return anchor.state
    gateway = gateway or ChainGateway(policy)
    try:
        _matches_policy(anchor, policy)
        if anchor.operation_type=='ISSUE' and anchor.signed_transaction is None and anchor.passport.status!='ACTIVE':
            return _record(anchor.pk,error=ProofError('CANCELLED_BEFORE_ANCHORING'))
        if anchor.operation_type=='ISSUE':
            _assert_stored_pdf(anchor)
        if anchor.depends_on_id:
            dependency=_rows().get(pk=anchor.depends_on_id)
            if not dependency.transaction_hash:
                return 'PENDING'
            try:
                gateway.verify(dependency)
            except ProofPending:
                return 'PENDING'
        if anchor.signed_transaction is None:
            if anchor.issuer_address!=policy.issuer_address:
                raise ProofError('SIGNER_ROTATION_REQUIRES_REVIEW')
            signer = signer or load_signer(policy)
            if signer.address.lower() != policy.issuer_address:
                raise ProofError('UNAPPROVED_SIGNING_KEY')
            anchor = _sign(anchor, gateway, signer)
        # Verify first: recover a crash after broadcast but before acknowledgement.
        try:
            proof = gateway.verify(anchor)
        except ProofPending:
            if gateway.submission_state(anchor)=='ABSENT':
                try:
                    tx_hash = gateway.broadcast(anchor.signed_transaction)
                    if tx_hash != anchor.transaction_hash:
                        raise ProofError('TRANSACTION_HASH_MISMATCH')
                except (ProofError,RPCUnavailable):
                    raise
                except Exception:
                    # Resolve an uncertain send using the durable hash, never a new signature.
                    pass
            proof = gateway.verify(anchor)
        return _record(anchor.pk, proof=proof)
    except ProofPending:
        return _record(anchor.pk, pending=True)
    except ProofError as error:
        return _record(anchor.pk, error=error)
    except ImproperlyConfigured:
        return _record(anchor.pk, error=ProofError('SIGNING_CONFIGURATION', retryable=True))
    except RPCDeadlineExceeded:
        return _record(anchor.pk,error=ProofError('RPC_TIMEOUT',retryable=True))
    except RPCUnavailable:
        return _record(anchor.pk,error=ProofError('RPC_UNAVAILABLE',retryable=True))
    except Exception:
        return _record(anchor.pk, error=ProofError('CHAIN_OR_STORAGE_UNAVAILABLE', retryable=True))


def process_batch(*, batch_size=20):
    if load_policy() is None:
        return {'disabled': True, 'processed': 0}
    key=Concat(Case(When(event_type='NAME_CHANGE',then=Value('replacement:')),default=Value('revocation:')),Cast('id',CharField()))
    intents=PassportLifecycleEvent.objects.annotate(_key=key).annotate(
        _queued=Exists(PassportAnchor.objects.filter(operation_key=OuterRef('_key')))
    ).filter(_queued=False).select_related('previous','replacement').order_by('created_at')[:batch_size]
    for event in intents:
        if event.event_type=='NAME_CHANGE':
            enqueue_replacement(event.previous,event.replacement,event)
        else:
            enqueue_revocation(event.previous,event)
    documents = PassportDocument.objects.select_related('passport_version').filter(
        status='ISSUED', passport_version__passport__status='ACTIVE', blockchain_anchor__isnull=True,
    ).order_by('created_at')[:batch_size]
    for document in documents:
        enqueue_document(document)
    ids = list(PassportAnchor.objects.filter(state__in=['PENDING','SIGNED','SUBMITTED']).filter(
        Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=timezone.now())
    ).order_by('created_at').values_list('pk', flat=True)[:batch_size])
    counts = {'processed': len(ids)}
    for anchor_id in ids:
        state = process_anchor(anchor_id)
        counts[state] = counts.get(state, 0) + 1
    return counts


def document_proof(document_reference,*,gateway=None,known_document=False):
    with rpc_budget(VERIFICATION_SECONDS):
        result=_document_proof(document_reference,gateway=gateway,known_document=known_document)
    result['assessed_at']=None if result['status']=='NOT_CONFIGURED' else timezone.now().isoformat()
    return result


def _document_proof(document_reference,*,gateway=None,known_document=False):
    result={'status':'PENDING_BLOCKCHAIN','blockchain_verified':False,'historical_blockchain_authentic':False,
            'issuer_key_authorized':False,'institutional_issuer_approved':False,'source':'POLYGON_PDF_COMMITMENT_V1'}
    try:
        policy=load_policy()
        if policy is None:
            if not known_document and document_reference is not None and not PassportDocument.objects.filter(public_reference=document_reference).exists():
                return {**result,'status':'NOT_FOUND'}
            return {**result,'status':'NOT_CONFIGURED'}
        if document_reference is None:
            return result
        anchor=_rows().filter(document__public_reference=document_reference,operation_type='ISSUE').first()
        if anchor is None:
            exists=PassportDocument.objects.filter(public_reference=document_reference).exists()
            return result if exists else {**result,'status':'NOT_FOUND'}
        _matches_policy(anchor,policy)
        result['institutional_issuer_approved']=True
        result.update(environment=policy.environment,chain_id=anchor.chain_id,
                      contract_address=anchor.contract_address,issuer_address=anchor.issuer_address,
                      passport_status=anchor.passport.status,pdf_sha256=anchor.pdf_sha256,
                      snapshot_sha256=anchor.snapshot_sha256,retryable=anchor.retryable,operation_state=anchor.state,
                      transaction_hash=anchor.transaction_hash or None,
                      operator_review_required=anchor.state=='FAILED' or anchor.error_code in ('STUCK_TRANSACTION_REVIEW_REQUIRED','NONCE_CONSUMED_REVIEW_REQUIRED'),
                      passport_key=anchor.passport_key,version_key=anchor.version_key,
                      document_key=anchor.document_key,commitment=anchor.commitment,
                      commitment_salt=anchor.commitment_salt)
        result.update(passport_reference=str(anchor.passport.public_reference),
                      version_reference=str(anchor.document.passport_version.public_reference))
        if not anchor.transaction_hash:
            return {**result,'status':'FAILED' if anchor.state=='FAILED' else 'PENDING_BLOCKCHAIN','error':anchor.error_code or None}
        gateway=gateway or ChainGateway(policy)
        proof=gateway.verify(anchor)
        if anchor.depends_on_id:
            dependency=_rows().get(pk=anchor.depends_on_id)
            if not dependency.transaction_hash:
                raise ProofPending()
            gateway.verify(dependency)
            result['replacement_transaction_hash']=dependency.transaction_hash
        # RPC can be slow; do not use lifecycle data read before it.
        latest=DigitalPassport.objects.values('status','latest_version_id','latest_version__version_number').get(pk=anchor.passport_id)
        result['passport_status']=latest['status']
        result['latest_version']=latest['latest_version__version_number']
        _issuer()
        from apps.verification.passport_service import PassportVerificationService
        registry=PassportVerificationService().verify(result['version_reference'],kind='version',include_blockchain=False)
        result['registry_status']=registry['status']
        result['credential_status']=registry['credential_status']
        valid_credentials=registry['authentic'] and (registry['credential_status']=='VALID' or registry['credential_membership_empty'])
        current=(latest['status']=='ACTIVE' and proof['onchain_status']=='ACTIVE'
                 and latest['latest_version_id']==anchor.document.passport_version_id and valid_credentials)
        return {**result,**proof,'transaction_hash':anchor.transaction_hash,'status':'CONFIRMED',
                'blockchain_verified':current,'historical_blockchain_authentic':True,'issuer_key_authorized':True}
    except ProofPending:
        failed=anchor.state=='FAILED'
        return {**result,'status':'FAILED' if failed else 'PENDING_BLOCKCHAIN','error':anchor.error_code or None}
    except ProofError as error:
        if error.code=='BTU_ISSUER_NOT_APPROVED':
            result['institutional_issuer_approved']=False
        return {**result,'status':'UNVERIFIABLE','error':error.code}
    except RPCDeadlineExceeded:
        return {**result,'status':'UNAVAILABLE','error':'RPC_TIMEOUT'}
    except RPCUnavailable:
        return {**result,'status':'UNAVAILABLE','error':'RPC_UNAVAILABLE'}
    except ImproperlyConfigured:
        return {**result,'status':'NOT_CONFIGURED','error':'INVALID_DEPLOYMENT_POLICY'}
    except Exception:
        return {**result,'status':'UNAVAILABLE'}


def version_proof(version_id):
    try:
        if load_policy() is None:
            return document_proof(None)
        document=PassportDocument.objects.filter(passport_version_id=version_id,status='ISSUED').order_by('-generation_number').first()
        return document_proof(document.public_reference if document else None)
    except ImproperlyConfigured:
        return document_proof(None)
    except Exception:
        return {'status':'UNAVAILABLE','blockchain_verified':False,'historical_blockchain_authentic':False,
                'issuer_key_authorized':False,'institutional_issuer_approved':False,'assessed_at':timezone.now().isoformat()}


def reconcile_confirmed(batch_size=20):
    policy=load_policy()
    if policy is None:
        return 0
    if connection.in_atomic_block:
        raise ImproperlyConfigured('Reconciliation must run outside database transactions.')
    rows=list(_rows().filter(state__in=['CONFIRMED','FAILED']).exclude(transaction_hash='').order_by(F('last_checked_at').asc(nulls_first=True),'created_at')[:batch_size])
    gateway=ChainGateway(policy)
    for row in rows:
        status,block_hash,error='CONFIRMED','',''
        try:
            with rpc_budget(VERIFICATION_SECONDS):
                _matches_policy(row,policy)
                proof=gateway.verify(row); block_hash=proof['block_hash']
                if row.state=='FAILED':
                    _record(row.pk,proof=proof)
        except ProofPending:
            status='PENDING_BLOCKCHAIN'
            if row.state=='CONFIRMED':
                try:
                    gateway.broadcast(row.signed_transaction)
                except Exception:
                    pass
        except ProofError as exc:
            status,error='UNVERIFIABLE',exc.code
        except Exception:
            status,error='UNAVAILABLE','RPC_UNAVAILABLE'
        previous=row.observations.order_by('-created_at').first()
        if previous is None or (previous.status,previous.block_hash,previous.error_code)!=(status,block_hash,error):
            ProofObservation.objects.create(operation=row,status=status,block_hash=block_hash,error_code=error)
        PassportAnchor.objects.filter(pk=row.pk).update(last_checked_at=timezone.now())
    return len(rows)


def retry_failed():
    count=0
    with transaction.atomic():
        for row in PassportAnchor.objects.select_for_update().filter(state='FAILED',retryable=True):
            row.state='SIGNED' if row.signed_transaction else 'PENDING'
            row.attempts,row.next_attempt_at,row.error_code=0,None,''
            row.save(update_fields=['state','attempts','next_attempt_at','error_code','updated_at'])
            count+=1
    return count
