from django.conf import settings


def apply_passport_proof(result,proof):
    result['blockchain']=proof
    if proof.get('passport_status') in ('REPLACED','REVOKED'):
        result['status']=proof['passport_status']; result['is_latest']=False
    if proof.get('onchain_status') in ('REPLACED','REVOKED'):
        result['status']=proof['onchain_status']; result['is_latest']=False
    if result['status'] in ('REPLACED','REVOKED','EXPIRED','INVALID','NOT_FOUND'):
        proof['blockchain_verified']=False
        return result
    if not getattr(settings,'PASSPORT_BLOCKCHAIN_ENFORCE',True):
        return result
    if proof.get('status') == 'CONFIRMED' and proof.get('historical_blockchain_authentic') is True:
        if (proof.get('institutional_issuer_approved') is not True
                or proof.get('issuer_key_authorized') is not True):
            proof['blockchain_verified']=False
            result['status']='UNVERIFIABLE'
            return result
        if result['status'] == 'VALID' and proof.get('blockchain_verified') is not True:
            result['status'] = 'UNVERIFIABLE'
    else:
        proof['blockchain_verified'] = False
        result['status']='PENDING_BLOCKCHAIN' if proof.get('status')=='PENDING_BLOCKCHAIN' else 'UNVERIFIABLE'
    if result['status'] != 'VALID':
        proof['blockchain_verified'] = False
    return result
