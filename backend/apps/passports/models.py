import uuid

from django.db import models
from django.db.models.functions import Now


class DigitalPassport(models.Model):
    """A student's permanent passport identity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    student = models.OneToOneField(
        "students.Student", on_delete=models.PROTECT, related_name="digital_passport"
    )
    latest_version = models.ForeignKey(
        "PassportVersion",
        on_delete=models.PROTECT,
        related_name="latest_for_passports",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "digital_passports"


class PassportVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ISSUED = "ISSUED", "Issued"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    passport = models.ForeignKey(
        DigitalPassport, on_delete=models.PROTECT, related_name="versions"
    )
    version_number = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    issued_at = models.DateTimeField(null=True, blank=True)
    content_sha256 = models.CharField(max_length=64, blank=True, default="")
    student_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "passport_versions"
        constraints = [
            models.UniqueConstraint(
                fields=["passport", "version_number"], name="uq_passport_version_number"
            ),
            models.CheckConstraint(
                condition=models.Q(version_number__gt=0), name="chk_passport_version_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["DRAFT", "ISSUED"]),
                name="chk_passport_version_status",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="DRAFT", issued_at__isnull=True, content_sha256="")
                    | models.Q(
                        status="ISSUED",
                        issued_at__isnull=False,
                        content_sha256__regex=r"^[0-9a-f]{64}$",
                    )
                ),
                name="chk_passport_version_issuance",
            ),
        ]


class PassportVersionCredential(models.Model):
    """Credential facts frozen when a passport version is issued."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(
        PassportVersion, on_delete=models.PROTECT, related_name="credential_snapshots"
    )
    credential = models.ForeignKey(
        "credentials.Credential",
        on_delete=models.PROTECT,
        related_name="passport_snapshots",
    )
    credential_public_reference = models.UUIDField()
    issuer_reference = models.CharField(max_length=255)
    issuer_name = models.CharField(max_length=255)
    credential_issued_at = models.DateTimeField()
    credential_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "passport_version_credentials"
        constraints = [
            models.UniqueConstraint(
                fields=["version", "credential"], name="uq_passport_version_credential"
            ),
        ]


class PassportVersionSkill(models.Model):
    """Skill catalog facts frozen when a passport version is issued."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    version = models.ForeignKey(
        PassportVersion, on_delete=models.PROTECT, related_name="skill_snapshots"
    )
    skill = models.ForeignKey(
        "skills.Skill", on_delete=models.PROTECT, related_name="passport_snapshots"
    )
    skill_code = models.CharField(max_length=100)
    skill_name = models.CharField(max_length=250)
    category = models.CharField(max_length=150)
    description = models.TextField()
    stamp_type = models.CharField(max_length=30)
    badge_asset_id = models.CharField(max_length=150)

    class Meta:
        db_table = "passport_version_skills"
        constraints = [
            models.UniqueConstraint(
                fields=["version", "skill"], name="uq_passport_version_skill"
            ),
        ]


class PassportVersionCredentialSkill(models.Model):
    """Preserves which represented skill came from which credential."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    credential_snapshot = models.ForeignKey(
        PassportVersionCredential, on_delete=models.PROTECT, related_name="skill_links"
    )
    skill_snapshot = models.ForeignKey(
        PassportVersionSkill, on_delete=models.PROTECT, related_name="credential_links"
    )

    class Meta:
        db_table = "passport_version_credential_skills"
        constraints = [
            models.UniqueConstraint(
                fields=["credential_snapshot", "skill_snapshot"],
                name="uq_passport_version_credential_skill",
            ),
        ]


class PassportUpdateEvent(models.Model):
    """Durable idempotency receipt for a logical passport refresh."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    passport = models.ForeignKey(
        DigitalPassport, on_delete=models.PROTECT, related_name="update_events"
    )
    version = models.ForeignKey(
        PassportVersion, on_delete=models.PROTECT, related_name="update_events"
    )
    event_key = models.CharField(max_length=255)
    content_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())

    class Meta:
        db_table = "passport_update_events"
        constraints = [
            models.UniqueConstraint(
                fields=["passport", "event_key"], name="uq_passport_update_event"
            ),
            models.CheckConstraint(
                condition=~models.Q(event_key=""), name="chk_passport_update_event_key"
            ),
            models.CheckConstraint(
                condition=models.Q(content_sha256__regex=r"^[0-9a-f]{64}$"),
                name="chk_passport_update_hash",
            ),
        ]
