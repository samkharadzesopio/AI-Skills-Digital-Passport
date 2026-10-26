"""Public verification of existing issued snapshots, with live credential validity."""
import re
from uuid import UUID
from django.utils import timezone
from apps.credentials.models import Credential
from apps.passports.models import PassportVersion
from .records import credential_record
from .services import CredentialVerificationService

MAX_PUBLIC_CREDENTIALS = 500


class PassportVerificationRepository:
    def version(self, reference, *, kind='passport', number=None):
        try:
            public = UUID(str(reference))
        except (ValueError, TypeError, AttributeError):
            return None
        rows = PassportVersion.objects
        if kind == 'version':
            rows = rows.filter(public_reference=public)
        elif number is not None:
            rows = rows.filter(passport__public_reference=public, version_number=number)
        else:
            from django.db.models import F
            rows = rows.filter(passport__public_reference=public, pk=F('passport__latest_version_id'))
        return rows.values('id', 'status', 'content_sha256', 'version_number',
                           'passport__status', 'passport__latest_version_id', 'passport__latest_version__version_number').first()

    def credentials(self, version_id):
        # Snapshot membership fixes the credential set; current status/trust comes
        # from authoritative Credential/Issuer rows, not mutable PDF metadata.
        return list(Credential.objects.filter(passport_snapshots__version_id=version_id)
                    .select_related('issuer').only('status', 'issued_at', 'expires_at',
                        'issuer_reference', 'issuer__reference', 'issuer__is_trusted')
                    .order_by('pk')[:MAX_PUBLIC_CREDENTIALS + 1])


class PassportVerificationService:
    def __init__(self, repository=None, clock=None):
        self.repository = repository or PassportVerificationRepository()
        self.clock = clock or timezone.now

    def verify(self, reference, *, kind='passport', number=None, include_blockchain=True):
        # Match the exact verification reference already printed by the renderer.
        if isinstance(reference, str) and reference.startswith('passport-version:'):
            reference, kind = reference.split(':', 1)[1], 'version'
        row = self.repository.version(reference, kind=kind, number=number)
        result = {'status': 'NOT_FOUND', 'authentic': False, 'is_latest': None,
                  'passport_version': None, 'latest_version': None,
                  'credential_status': 'UNVERIFIABLE', 'credential_counts': {},
                  'credential_membership_empty': False,
                  'source': 'POSTGRESQL_PASSPORT_REGISTRY'}
        if row is None:
            return result
        result['status'] = 'UNVERIFIABLE'
        latest = row['passport__latest_version__version_number']
        if row['status'] != 'ISSUED' or not re.fullmatch(r'[0-9a-f]{64}', row['content_sha256'] or '') or latest is None or latest < row['version_number']:
            return result
        result.update(authentic=True, is_latest=row['id'] == row['passport__latest_version_id'],
                      passport_version=row['version_number'], latest_version=latest)
        lifecycle=row.get('passport__status','ACTIVE')
        if lifecycle!='ACTIVE':
            result.update(status=lifecycle,is_latest=False)
            return self._with_proof(result,row['id'],include_blockchain)
        credentials = self.repository.credentials(row['id'])
        if not credentials or len(credentials) > MAX_PUBLIC_CREDENTIALS:
            result['credential_membership_empty'] = not credentials
            return self._with_proof(result, row['id'], include_blockchain)
        counts = dict.fromkeys(['VALID', 'REVOKED', 'EXPIRED', 'INVALID'], 0)
        now = self.clock()
        verifier = CredentialVerificationService(clock=lambda: now)
        for credential in credentials:
            status = verifier.verify_record(credential_record(credential))['status']
            counts[status] += 1
        aggregate = next((s for s in ['REVOKED', 'INVALID', 'EXPIRED'] if counts[s]), 'VALID')
        result['credential_counts'], result['credential_status'] = counts, aggregate
        result['status'] = ('VALID' if result['is_latest'] else 'OUTDATED') if aggregate == 'VALID' else aggregate
        return self._with_proof(result, row['id'], include_blockchain)

    def _with_proof(self,result, version_id, include_blockchain):
        if include_blockchain:
            from apps.blockchain.services import version_proof
            from .blockchain_policy import apply_passport_proof
            proof=version_proof(version_id)
            if proof.get('version_reference'):
                result=self.verify(proof['version_reference'],kind='version',include_blockchain=False)
            return apply_passport_proof(result,proof)
        return result
