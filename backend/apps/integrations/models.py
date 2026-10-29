"""Durable inbox, not a second achievement or credential ledger."""
import uuid
from django.conf import settings
from django.db import models


class ClassroomSyncEvent(models.Model):
    class State(models.TextChoices):
        RECEIVED = 'RECEIVED'
        PROCESSING = 'PROCESSING'
        ACHIEVEMENTS_RECORDED = 'ACHIEVEMENTS_RECORDED'
        CREDENTIAL_ISSUED = 'CREDENTIAL_ISSUED'
        FAILED = 'FAILED'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=100)
    source_event_id = models.CharField(max_length=120)
    payload = models.JSONField()
    payload_sha256 = models.CharField(max_length=64)
    mapping_snapshot = models.JSONField(null=True)
    issuer_reference = models.CharField(max_length=255, blank=True)
    state = models.CharField(max_length=32, choices=State.choices, default=State.RECEIVED)
    achievement_event = models.OneToOneField(
        'skills.AchievementSourceEvent', null=True, on_delete=models.PROTECT,
        related_name='classroom_sync',
    )
    credential = models.OneToOneField(
        'credentials.Credential', null=True, on_delete=models.PROTECT,
        related_name='classroom_sync',
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    retryable = models.BooleanField(default=False)
    next_retry_at = models.DateTimeField(null=True)
    error_code = models.CharField(max_length=64, blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['source', 'source_event_id'], name='uq_classroom_sync_source_event'),
            models.CheckConstraint(condition=models.Q(source__in=['BTU_CLASSROOM', 'BTU_EXCEL', 'BTU_GOOGLE_SHEETS']), name='chk_classroom_sync_source'),
            models.CheckConstraint(condition=models.Q(payload_sha256__regex=r'^[0-9a-f]{64}$'), name='chk_classroom_sync_hash'),
            models.CheckConstraint(condition=models.Q(attempts__lte=5), name='chk_classroom_sync_attempts'),
            models.CheckConstraint(condition=~models.Q(state='CREDENTIAL_ISSUED') | models.Q(
                credential__isnull=False, achievement_event__isnull=False,
            ), name='chk_classroom_sync_issued_links'),
            models.CheckConstraint(condition=models.Q(state__in=[
                'RECEIVED', 'PROCESSING', 'ACHIEVEMENTS_RECORDED', 'CREDENTIAL_ISSUED', 'FAILED',
            ]), name='chk_classroom_sync_state'),
        ]
        indexes = [models.Index(fields=['state', 'next_retry_at'], name='classroom_sync_retry_idx')]


class ImportRun(models.Model):
    source = models.CharField(max_length=100)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='completion_imports')
    state = models.CharField(max_length=16, default='RUNNING')
    summary = models.JSONField(default=dict)
    validation_errors = models.JSONField(default=list)
    events = models.ManyToManyField(ClassroomSyncEvent, related_name='import_runs')
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)


class SpreadsheetProfile(models.Model):
    """Operator-provisioned, immutable version of an institutional source policy."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.SlugField(max_length=80)
    version = models.PositiveIntegerField()
    source = models.CharField(max_length=30, choices=[('BTU_EXCEL', 'Excel'), ('BTU_GOOGLE_SHEETS', 'Google Sheets')])
    kind = models.CharField(max_length=16, choices=[('COMPLETION', 'Completion'), ('SKILL_AWARD', 'Skill award')])
    definition = models.JSONField()
    definition_sha256 = models.CharField(max_length=64)
    approval_reference = models.CharField(max_length=255)
    enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['key', 'version'], name='uq_spreadsheet_profile_version'),
            models.CheckConstraint(condition=models.Q(version__gte=1), name='chk_spreadsheet_profile_version'),
            models.CheckConstraint(condition=models.Q(source__in=['BTU_EXCEL', 'BTU_GOOGLE_SHEETS']), name='chk_spreadsheet_profile_source'),
            models.CheckConstraint(condition=models.Q(kind__in=['COMPLETION', 'SKILL_AWARD']), name='chk_spreadsheet_profile_kind'),
            models.CheckConstraint(condition=models.Q(definition_sha256__regex=r'^[0-9a-f]{64}$'), name='chk_spreadsheet_profile_hash'),
        ]


class SpreadsheetPreview(models.Model):
    """Private reviewed snapshot. No uploaded workbook or source PII is returned."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    profile = models.ForeignKey(SpreadsheetProfile, on_delete=models.PROTECT)
    source_sha256 = models.CharField(max_length=64)
    snapshot_sha256 = models.CharField(max_length=64)
    records = models.JSONField(default=list)
    report = models.JSONField(default=dict)
    state = models.CharField(max_length=16, default='READY')
    attempts = models.PositiveSmallIntegerField(default=0)
    lease_token = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    confirmed_at = models.DateTimeField(null=True)
    expires_at = models.DateTimeField()
    run = models.OneToOneField(ImportRun, null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(state__in=['READY', 'PROCESSING', 'COMPLETED', 'FAILED']), name='chk_spreadsheet_preview_state'),
            models.CheckConstraint(condition=models.Q(attempts__lte=5), name='chk_spreadsheet_preview_attempts'),
        ]


class SpreadsheetAward(models.Model):
    """Atomic skill-evidence receipt; uses the existing achievement/credential ledger."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=30)
    profile_key = models.CharField(max_length=80)
    namespace = models.CharField(max_length=80)
    record_id = models.CharField(max_length=120)
    payload_sha256 = models.CharField(max_length=64)
    payload = models.JSONField()
    profile = models.ForeignKey(SpreadsheetProfile, on_delete=models.PROTECT)
    achievement_event = models.OneToOneField('skills.AchievementSourceEvent', on_delete=models.PROTECT)
    credential = models.OneToOneField('credentials.Credential', on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['namespace', 'record_id'], name='uq_spreadsheet_award_record'),
        ]


class SpreadsheetAutomation(models.Model):
    """Continuing administrator authority for one independently approved policy."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.OneToOneField(SpreadsheetProfile, on_delete=models.PROTECT, related_name='automation')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='spreadsheet_automations')
    authorization_reference = models.CharField(max_length=255)
    enabled = models.BooleanField(default=False)
    interval_seconds = models.PositiveIntegerField(default=300)
    next_poll_at = models.DateTimeField()
    source_sha256 = models.CharField(max_length=64, blank=True)
    approved_target_sha256 = models.CharField(max_length=64, blank=True)
    lease_token = models.UUIDField(null=True)
    lease_until = models.DateTimeField(null=True)
    last_checked_at = models.DateTimeField(null=True)
    last_state = models.CharField(max_length=20, default='IDLE')
    last_error_code = models.CharField(max_length=100, blank=True)
    approved_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(interval_seconds__gte=60, interval_seconds__lte=86400), name='chk_spreadsheet_auto_interval')]
        indexes = [models.Index(fields=['enabled', 'next_poll_at'], name='spreadsheet_auto_due_idx')]


class SpreadsheetPoll(models.Model):
    """Sanitized durable worker history; private source facts stay in existing snapshots."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    automation = models.ForeignKey(SpreadsheetAutomation, on_delete=models.PROTECT, related_name='polls')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='spreadsheet_polls')
    audit = models.OneToOneField('accounts.SecurityAudit', on_delete=models.PROTECT)
    lease_token = models.UUIDField()
    state = models.CharField(max_length=20, default='PROCESSING')
    source_sha256 = models.CharField(max_length=64, blank=True)
    preview = models.ForeignKey(SpreadsheetPreview, null=True, on_delete=models.PROTECT)
    counts = models.JSONField(default=dict)
    error_code = models.CharField(max_length=100, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True)

    class Meta:
        indexes = [models.Index(fields=['automation', '-started_at'], name='spreadsheet_poll_history_idx')]
