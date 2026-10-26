import uuid

from django.db import models


class PassportAnchor(models.Model):
    """One immutable target and one durably signed transaction per PDF artifact."""
    class State(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SIGNED = 'SIGNED', 'Signed'
        SUBMITTED = 'SUBMITTED', 'Submitted'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        FAILED = 'FAILED', 'Failed'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.OneToOneField('passports.PassportDocument', null=True, on_delete=models.PROTECT, related_name='blockchain_anchor')
    passport = models.ForeignKey('passports.DigitalPassport', on_delete=models.PROTECT, related_name='chain_operations')
    replacement = models.ForeignKey('passports.DigitalPassport', null=True, on_delete=models.PROTECT, related_name='chain_replacements')
    depends_on = models.ForeignKey('self', null=True, on_delete=models.PROTECT)
    operation_type = models.CharField(max_length=10, choices=[('ISSUE','Issue'),('REPLACE','Replace'),('REVOKE','Revoke')])
    operation_key = models.CharField(max_length=200, unique=True)
    passport_key = models.CharField(max_length=64)
    version_key = models.CharField(max_length=64, blank=True)
    document_key = models.CharField(max_length=64, blank=True)
    commitment = models.CharField(max_length=64, blank=True)
    commitment_salt = models.CharField(max_length=64, blank=True)
    replacement_key = models.CharField(max_length=64, blank=True)
    issuer = models.ForeignKey('credentials.CredentialIssuer', on_delete=models.PROTECT)
    pdf_sha256 = models.CharField(max_length=64, blank=True)
    snapshot_sha256 = models.CharField(max_length=64, blank=True)
    chain_id = models.PositiveBigIntegerField()
    contract_address = models.CharField(max_length=42)
    issuer_address = models.CharField(max_length=42)
    state = models.CharField(max_length=10, choices=State.choices, default=State.PENDING)
    signed_transaction = models.BinaryField(null=True, editable=False)
    transaction_hash = models.CharField(max_length=66, blank=True)
    nonce = models.PositiveBigIntegerField(null=True)
    block_number = models.PositiveBigIntegerField(null=True)
    block_hash = models.CharField(max_length=66, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    retryable = models.BooleanField(default=True)
    next_attempt_at = models.DateTimeField(null=True)
    error_code = models.CharField(max_length=50, blank=True)
    last_checked_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'passport_blockchain_anchors'
        constraints = [
            models.UniqueConstraint(fields=['chain_id', 'issuer_address', 'nonce'], name='uq_anchor_signer_nonce'),
            models.CheckConstraint(condition=models.Q(pdf_sha256__regex=r'^[0-9a-f]{64}$') | models.Q(document__isnull=True, pdf_sha256=''), name='chk_anchor_pdf_hash'),
            models.CheckConstraint(condition=models.Q(chain_id__gt=0), name='chk_anchor_positive_chain'),
            models.CheckConstraint(condition=models.Q(contract_address__regex=r'^0x[0-9a-f]{40}$') & models.Q(issuer_address__regex=r'^0x[0-9a-f]{40}$'), name='chk_anchor_addresses'),
            models.CheckConstraint(condition=models.Q(state__in=['PENDING','SIGNED','SUBMITTED','CONFIRMED','FAILED']), name='chk_anchor_state'),
            models.CheckConstraint(condition=(
                models.Q(signed_transaction__isnull=True, nonce__isnull=True, transaction_hash='')
                | (models.Q(signed_transaction__isnull=False, nonce__isnull=False) & models.Q(transaction_hash__regex=r'^0x[0-9a-f]{64}$'))
            ), name='chk_anchor_signature'),
            models.CheckConstraint(condition=(
                ~models.Q(state='CONFIRMED')
                | (models.Q(block_number__isnull=False, signed_transaction__isnull=False) & models.Q(block_hash__regex=r'^0x[0-9a-f]{64}$'))
            ), name='chk_anchor_confirmation'),
        ]
        indexes = [models.Index(fields=['state', 'next_attempt_at', 'created_at'], name='anchor_due_idx')]


class SignerNonce(models.Model):
    """Serializes nonce reservations across processes sharing this signing key."""
    key = models.CharField(max_length=100, primary_key=True)
    next_nonce = models.PositiveBigIntegerField(default=0)

    class Meta:
        db_table = 'blockchain_signer_nonces'


class ProofObservation(models.Model):
    operation=models.ForeignKey(PassportAnchor,on_delete=models.PROTECT,related_name='observations')
    status=models.CharField(max_length=30)
    block_hash=models.CharField(max_length=66,blank=True)
    error_code=models.CharField(max_length=50,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table='blockchain_proof_observations'
        indexes=[models.Index(fields=['operation','-created_at'],name='proof_observation_latest_idx')]
