"""Add default-off source authority and sanitized polling history only."""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ('integrations', '0004_spreadsheet_integrity'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SpreadsheetAutomation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('authorization_reference', models.CharField(max_length=255)),
                ('enabled', models.BooleanField(default=False)),
                ('interval_seconds', models.PositiveIntegerField(default=300)),
                ('next_poll_at', models.DateTimeField()),
                ('source_sha256', models.CharField(blank=True, max_length=64)),
                ('approved_target_sha256', models.CharField(blank=True, max_length=64)),
                ('lease_token', models.UUIDField(null=True)),
                ('lease_until', models.DateTimeField(null=True)),
                ('last_checked_at', models.DateTimeField(null=True)),
                ('last_state', models.CharField(default='IDLE', max_length=20)),
                ('last_error_code', models.CharField(blank=True, max_length=100)),
                ('approved_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='spreadsheet_automations', to=settings.AUTH_USER_MODEL)),
                ('profile', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name='automation', to='integrations.spreadsheetprofile')),
            ],
            options={
                'indexes': [models.Index(fields=['enabled', 'next_poll_at'], name='spreadsheet_auto_due_idx')],
                'constraints': [models.CheckConstraint(condition=models.Q(interval_seconds__gte=60, interval_seconds__lte=86400), name='chk_spreadsheet_auto_interval')],
            },
        ),
        migrations.CreateModel(
            name='SpreadsheetPoll',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('lease_token', models.UUIDField()),
                ('state', models.CharField(default='PROCESSING', max_length=20)),
                ('source_sha256', models.CharField(blank=True, max_length=64)),
                ('counts', models.JSONField(default=dict)),
                ('error_code', models.CharField(blank=True, max_length=100)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('finished_at', models.DateTimeField(null=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='spreadsheet_polls', to=settings.AUTH_USER_MODEL)),
                ('audit', models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, to='accounts.securityaudit')),
                ('automation', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='polls', to='integrations.spreadsheetautomation')),
                ('preview', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='integrations.spreadsheetpreview')),
            ],
            options={'indexes': [models.Index(fields=['automation', '-started_at'], name='spreadsheet_poll_history_idx')]},
        ),
    ]
