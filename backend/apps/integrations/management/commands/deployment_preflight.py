"""Read-only rollout gate. Never migrates, provisions issuers or sends mail."""
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from apps.credentials.models import CredentialIssuer


class Command(BaseCommand):
    help = 'Read-only schema/policy preflight; does not approve migration or deployment.'

    def handle(self, *args, **options):
        errors = []
        if connection.vendor != 'postgresql':
            errors.append('PostgreSQL is required.')
        if getattr(settings, 'DEBUG', False):
            errors.append('DEBUG must be false for deployment.')
        if getattr(settings, 'ACCOUNTS_ALLOW_TEST_EMAIL', False) or getattr(settings, 'ACCOUNTS_ALLOW_UNSAFE_TEST_DB', False):
            errors.append('Test authentication bypasses must be disabled.')
        if not getattr(settings, 'SESSION_COOKIE_SECURE', False) or not getattr(settings, 'CSRF_COOKIE_SECURE', False):
            errors.append('Secure session/CSRF cookies are required.')
        if not getattr(settings, 'SECURE_SSL_REDIRECT', False):
            errors.append('HTTPS redirect is required.')
        if getattr(settings, 'EMAIL_BACKEND', '') != 'django.core.mail.backends.smtp.EmailBackend' or not getattr(settings, 'EMAIL_HOST', ''):
            errors.append('Configure TLS SMTP delivery before deployment.')
        if not (getattr(settings, 'EMAIL_USE_TLS', False) or getattr(settings, 'EMAIL_USE_SSL', False)):
            errors.append('SMTP transport encryption is required.')
        ref = getattr(settings, 'BTU_CLASSROOM_ISSUER_REFERENCE', '')
        approved = getattr(settings, 'VERIFICATION_TRUSTED_ISSUER_REFERENCES', ())
        if not ref or not isinstance(approved, (list, tuple)) or ref not in approved:
            errors.append('Confirm an issuance reference and public issuer allowlist.')
        statuses = getattr(settings, 'ACCOUNTS_ACTIVE_STUDENT_STATUSES', ())
        if not statuses:
            errors.append('Confirm the exact eligible Student status values.')
        sources = getattr(settings, 'BTU_AUTHORIZED_COMPLETION_SOURCES', ())
        if not isinstance(sources, (list, tuple)) or set(sources) - {'BTU_EXCEL', 'BTU_GOOGLE_SHEETS'}:
            errors.append('Invalid institutional source policy.')
        if 'BTU_GOOGLE_SHEETS' in sources:
            path = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE', '')
            if not getattr(settings, 'BTU_GOOGLE_SHEET_ID', '') or not path or not Path(path).is_file():
                errors.append('Google source settings or secure credential file are missing.')
        try:
            executor = MigrationExecutor(connection)
            if executor.migration_plan(executor.loader.graph.leaf_nodes()):
                errors.append('Unapplied migrations: obtain review/approval before applying them.')
            elif ref and not CredentialIssuer.objects.filter(reference=ref, is_trusted=True).exists():
                errors.append('The fixed BTU issuer must be provisioned and trusted.')
        except Exception:
            errors.append('Cannot read database migration/issuer state; no deployment readiness established.')
        if errors:
            raise CommandError('\n'.join(errors))
        self.stdout.write(self.style.SUCCESS('Read-only preflight passed. Live delivery, worker health and institutional data still need smoke tests.'))
