import uuid

from django.db import models
from django.db.models.functions import Now
from django.utils import timezone


BTU_ISSUER_REFERENCE = "BTU-UNIVERSITY"
BTU_ISSUER_DISPLAY_NAME = "Business and Technology University"


class CredentialIssuer(models.Model):
    """Issuer identity; only the fixed BTU identity may issue credentials."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255)
    is_trusted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "credential_issuers"
        constraints = [
            models.CheckConstraint(condition=~models.Q(reference=""), name="chk_credential_issuer_ref"),
            models.CheckConstraint(condition=~models.Q(display_name=""), name="chk_credential_issuer_name"),
            models.CheckConstraint(
                condition=models.Q(is_trusted=False)
                | models.Q(reference=BTU_ISSUER_REFERENCE),
                name="chk_credential_issuer_trust_ref",
            ),
            models.UniqueConstraint(
                fields=["is_trusted"],
                condition=models.Q(is_trusted=True),
                name="uq_single_trusted_issuer",
            ),
        ]


class Credential(models.Model):
    class Status(models.TextChoices):
        ISSUED = "ISSUED", "Issued"
        REVOKED = "REVOKED", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="credentials", db_index=False)
    issuer = models.ForeignKey(CredentialIssuer, on_delete=models.PROTECT, related_name="credentials")
    issuer_reference = models.CharField(max_length=255)
    issuer_name = models.CharField(max_length=255)
    idempotency_key = models.CharField(max_length=255)
    request_sha256 = models.CharField(max_length=64)
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ISSUED)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.TextField(blank=True, default="")
    revoked_by = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    achievements = models.ManyToManyField("skills.VerifiedAchievement", through="CredentialAchievement", related_name="credentials")

    class Meta:
        db_table = "credentials"
        constraints = [
            models.UniqueConstraint(fields=["issuer_reference", "idempotency_key"], name="uq_credential_issuer_idem"),
            models.CheckConstraint(condition=models.Q(status__in=["ISSUED", "REVOKED"]), name="chk_credential_status"),
            models.CheckConstraint(condition=~models.Q(idempotency_key=""), name="chk_credential_idempotency"),
            models.CheckConstraint(condition=models.Q(request_sha256__regex=r"^[0-9a-f]{64}$"), name="chk_credential_fingerprint"),
            models.CheckConstraint(
                condition=(models.Q(status="ISSUED", revoked_at__isnull=True, revoked_by="", revocation_reason="") |
                           models.Q(status="REVOKED", revoked_at__isnull=False, revoked_by__gt="", revocation_reason__gt="")),
                name="chk_credential_revocation_state",
            ),
            models.CheckConstraint(condition=models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=models.F("issued_at")), name="chk_credential_expiry"),
        ]
        indexes = [
            models.Index(fields=["student", "-issued_at"], name="cred_student_issued_idx"),
            models.Index(
                fields=["expires_at"],
                condition=models.Q(status="ISSUED", expires_at__isnull=False),
                name="cred_issued_expiry_idx",
            ),
        ]

    def verification_status_at(self, now):
        if self.status == self.Status.REVOKED:
            return "REVOKED"
        if self.status != self.Status.ISSUED or self.issued_at > now:
            return "INVALID"
        if self.expires_at is not None and now >= self.expires_at:
            return "EXPIRED"
        return "VALID"


class CredentialAchievement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    credential = models.ForeignKey(Credential, on_delete=models.PROTECT, related_name="achievement_links")
    achievement = models.ForeignKey("skills.VerifiedAchievement", on_delete=models.PROTECT, related_name="credential_links")

    class Meta:
        db_table = "credential_achievements"
        constraints = [models.UniqueConstraint(fields=["credential", "achievement"], name="uq_credential_achievement")]


class CredentialLifecycleEvent(models.Model):
    class EventType(models.TextChoices):
        ISSUED = "ISSUED", "Issued"
        REVOKED = "REVOKED", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    credential = models.ForeignKey(Credential, on_delete=models.PROTECT, related_name="lifecycle_events")
    event_type = models.CharField(max_length=10, choices=EventType.choices)
    occurred_at = models.DateTimeField()
    actor_reference = models.CharField(max_length=255)
    reason = models.TextField(blank=True, default="")

    class Meta:
        db_table = "credential_lifecycle_events"
        constraints = [
            models.UniqueConstraint(fields=["credential", "event_type"], name="uq_credential_lifecycle_type"),
            models.CheckConstraint(condition=models.Q(event_type__in=["ISSUED", "REVOKED"]), name="chk_credential_event_type"),
            models.CheckConstraint(condition=~models.Q(actor_reference=""), name="chk_credential_event_actor"),
        ]


class CredentialPassportRefresh(models.Model):
    """Transactional outbox entry for a current Passport snapshot refresh."""

    class SourceType(models.TextChoices):
        CREDENTIAL_LIFECYCLE = "CREDENTIAL_LIFECYCLE", "Credential lifecycle"
        EXPIRATION = "EXPIRATION", "Credential expiration"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_key = models.CharField(max_length=255, unique=True)
    source_type = models.CharField(max_length=24, choices=SourceType.choices)
    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="credential_passport_refreshes",
    )
    lifecycle_event = models.OneToOneField(
        CredentialLifecycleEvent,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="passport_refresh",
    )
    source_occurred_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    available_at = models.DateTimeField(default=timezone.now, db_default=Now())
    lease_token = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=8)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=100, blank=True, default="")
    last_error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "credential_passport_refreshes"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(source_type__in=["CREDENTIAL_LIFECYCLE", "EXPIRATION"]),
                name="chk_cred_refresh_source_type",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(source_type="CREDENTIAL_LIFECYCLE", lifecycle_event__isnull=False)
                    | models.Q(source_type="EXPIRATION", lifecycle_event__isnull=True)
                ),
                name="chk_cred_refresh_source_link",
            ),
            models.CheckConstraint(
                condition=models.Q(event_key__gt=""),
                name="chk_cred_refresh_event_key",
            ),
            models.CheckConstraint(
                condition=models.Q(max_attempts__gte=1, max_attempts__lte=50)
                & models.Q(attempt_count__lte=models.F("max_attempts")),
                name="chk_cred_refresh_attempt_limits",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="PENDING",
                        lease_token__isnull=True,
                        lease_expires_at__isnull=True,
                        completed_at__isnull=True,
                        attempt_count__lt=models.F("max_attempts"),
                    )
                    | models.Q(
                        status="PROCESSING",
                        lease_token__isnull=False,
                        lease_expires_at__isnull=False,
                        completed_at__isnull=True,
                        attempt_count__gt=0,
                    )
                    | models.Q(
                        status="COMPLETED",
                        lease_token__isnull=True,
                        lease_expires_at__isnull=True,
                        completed_at__isnull=False,
                        last_error_code="",
                        last_error_message="",
                    )
                    | models.Q(
                        status="FAILED",
                        lease_token__isnull=True,
                        lease_expires_at__isnull=True,
                        completed_at__isnull=True,
                        attempt_count=models.F("max_attempts"),
                        last_error_code__gt="",
                        last_error_message__gt="",
                    )
                ),
                name="chk_cred_refresh_state",
            ),
        ]
        indexes = [
            models.Index(
                fields=["available_at", "created_at"],
                condition=models.Q(status="PENDING"),
                name="cred_refresh_pending_idx",
            ),
            models.Index(
                fields=["lease_expires_at"],
                condition=models.Q(status="PROCESSING"),
                name="cred_refresh_lease_idx",
            ),
            models.Index(
                fields=["created_at"],
                condition=models.Q(status="FAILED"),
                name="cred_refresh_failed_idx",
            ),
        ]


class CredentialIssuerProvisioningEvent(models.Model):
    class EventType(models.TextChoices):
        PROVISIONED = "PROVISIONED", "Provisioned"
        DISPLAY_NAME_CHANGED = "DISPLAY_NAME_CHANGED", "Display name changed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    issuer = models.ForeignKey(
        CredentialIssuer,
        on_delete=models.PROTECT,
        related_name="provisioning_events",
    )
    actor_user_id = models.CharField(max_length=36)
    actor_email = models.EmailField(max_length=254)
    event_type = models.CharField(max_length=24, choices=EventType.choices)
    previous_display_name = models.CharField(max_length=255, blank=True, default="")
    display_name = models.CharField(max_length=255)
    occurred_at = models.DateTimeField(default=timezone.now, db_default=Now())

    class Meta:
        db_table = "credential_issuer_provisioning_events"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(event_type__in=["PROVISIONED", "DISPLAY_NAME_CHANGED"]),
                name="chk_issuer_provision_event_type",
            ),
            models.CheckConstraint(
                condition=models.Q(actor_user_id__gt="") & models.Q(actor_email__gt=""),
                name="chk_issuer_provision_actor",
            ),
            models.CheckConstraint(
                condition=models.Q(display_name__gt=""),
                name="chk_issuer_provision_display_name",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(event_type="PROVISIONED", previous_display_name="")
                    | models.Q(
                        event_type="DISPLAY_NAME_CHANGED",
                        previous_display_name__gt="",
                    )
                ),
                name="chk_issuer_provision_previous_name",
            ),
            models.CheckConstraint(
                condition=~models.Q(previous_display_name=models.F("display_name")),
                name="chk_issuer_provision_name_changed",
            ),
        ]
        indexes = [
            models.Index(
                fields=["issuer", "-occurred_at"],
                name="issuer_provision_audit_idx",
            ),
        ]
