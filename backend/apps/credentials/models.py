import uuid

from django.db import models
from django.db.models.functions import Now


class CredentialIssuer(models.Model):
    """Issuer identity provisioned through trusted operator configuration."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=255, unique=True)
    display_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "credential_issuers"
        constraints = [
            models.CheckConstraint(condition=~models.Q(reference=""), name="chk_credential_issuer_ref"),
            models.CheckConstraint(condition=~models.Q(display_name=""), name="chk_credential_issuer_name"),
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
        indexes = [models.Index(fields=["student", "-issued_at"], name="cred_student_issued_idx")]

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
