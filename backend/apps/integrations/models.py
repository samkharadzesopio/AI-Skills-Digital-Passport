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
