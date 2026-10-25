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
    source_occurred_at = models.DateTimeField(null=True, blank=True)
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


class PassportDocument(models.Model):
    """Metadata and durable generation state for one stored PDF artifact."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        GENERATING = "GENERATING", "Generating"
        ISSUED = "ISSUED", "Issued"
        FAILED = "FAILED", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    passport_version = models.ForeignKey(
        PassportVersion,
        on_delete=models.PROTECT,
        related_name="documents",
    )
    generation_number = models.PositiveIntegerField()
    renderer_version = models.CharField(max_length=50)
    request_sha256 = models.CharField(max_length=64)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    storage_key = models.CharField(max_length=500, blank=True, default="")
    attempt_storage_key = models.CharField(max_length=500, blank=True, default="")
    pdf_sha256 = models.CharField(max_length=64, blank=True, default="")
    byte_size = models.PositiveIntegerField(null=True, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    error_code = models.CharField(max_length=100, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    class Meta:
        db_table = "passport_documents"
        constraints = [
            models.UniqueConstraint(
                fields=["passport_version", "generation_number"],
                name="uq_passport_document_generation",
            ),
            models.UniqueConstraint(
                fields=["passport_version", "request_sha256"],
                name="uq_passport_document_request",
            ),
            models.UniqueConstraint(
                fields=["storage_key"],
                condition=~models.Q(storage_key=""),
                name="uq_passport_document_storage_key",
            ),
            models.CheckConstraint(
                condition=models.Q(generation_number__gt=0),
                name="chk_passport_document_generation",
            ),
            models.CheckConstraint(
                condition=models.Q(request_sha256__regex=r"^[0-9a-f]{64}$"),
                name="chk_passport_document_request_hash",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["PENDING", "GENERATING", "ISSUED", "FAILED"]
                ),
                name="chk_passport_document_status",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status="PENDING",
                        storage_key="",
                        attempt_storage_key="",
                        pdf_sha256="",
                        byte_size__isnull=True,
                        generated_at__isnull=True,
                        lease_token__isnull=True,
                        lease_expires_at__isnull=True,
                        attempt_count=0,
                        error_code="",
                        error_message="",
                    )
                    | models.Q(
                        status="GENERATING",
                        storage_key="",
                        pdf_sha256="",
                        byte_size__isnull=True,
                        generated_at__isnull=True,
                        lease_token__isnull=False,
                        lease_expires_at__isnull=False,
                        attempt_count__gt=0,
                        error_code="",
                        error_message="",
                    )
                    | models.Q(
                        status="ISSUED",
                        storage_key=models.F("attempt_storage_key"),
                        pdf_sha256__regex=r"^[0-9a-f]{64}$",
                        byte_size__gt=0,
                        generated_at__isnull=False,
                        lease_token__isnull=True,
                        lease_expires_at__isnull=True,
                        error_code="",
                        error_message="",
                    )
                    | models.Q(
                        status="FAILED",
                        storage_key="",
                        pdf_sha256="",
                        byte_size__isnull=True,
                        generated_at__isnull=True,
                        lease_token__isnull=True,
                        lease_expires_at__isnull=True,
                        attempt_count__gt=0,
                        error_code__gt="",
                        error_message__gt="",
                    )
                ),
                name="chk_passport_document_state",
            ),
        ]
        indexes = [
            models.Index(
                fields=["passport_version", "status", "-generation_number"],
                name="passdoc_version_status_idx",
            ),
            models.Index(
                fields=["pdf_sha256"],
                condition=models.Q(status="ISSUED"),
                name="passdoc_issued_hash_idx",
            ),
        ]
