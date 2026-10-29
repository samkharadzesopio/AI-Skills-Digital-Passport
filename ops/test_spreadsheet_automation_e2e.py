"""Native Chrome/Django/PostgreSQL automatic discovery, synthetic provider only.

Run against a newly allocated local cluster, for example the audit's
run_validation.py. DisposableRun refuses existing databases and removes its own
database/media/server. No real Google, email, authentication changes or chain.
"""
import contextvars
import copy
import json
import os
from pathlib import Path
import secrets
import sys
import threading
from unittest.mock import patch
from wsgiref.simple_server import make_server, WSGIRequestHandler

from disposable_tests import DisposableRun, test_database_name

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'apps.integrations.postgres_test_settings'
os.environ['INTEGRATION_TEST_DB_NAME'] = test_database_name('sheet_auto')
import django
django.setup()
from django.conf import settings
from django.core.wsgi import get_wsgi_application
from django.db import close_old_connections, connections
from django.test import override_settings
from apps.accounts.models import User
from apps.credentials.models import Credential
from apps.credentials.test_support import create_test_issuer
from apps.integrations.importers.mapping import digest
from apps.integrations.importers.profiles import provision_profile
from apps.integrations.models import SpreadsheetAutomation, SpreadsheetAward, SpreadsheetPoll
from apps.integrations.spreadsheet_automation import poll_due_sources
from apps.integrations.test_spreadsheet_mapping import definition, grid, ROW
from apps.passports.models import DigitalPassport, PassportVersion
from apps.skills.models import Skill
from apps.students.models import Student


class Quiet(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def main():
    if not os.environ.get('BTU_BROWSER_TOOLS'):
        raise RuntimeError('Provide the isolated Playwright installation.')
    with DisposableRun() as owned:
        owned.database()
        directory = Path(settings.MEDIA_ROOT)
        target = {'spreadsheet_id': 'SYNTHETIC_AUTO_NO_GOOGLE', 'worksheet': 'Passport Skill Records', 'range': 'A1:F20'}
        owned.enter_context(override_settings(ROOT_URLCONF='config.urls', ALLOWED_HOSTS=['127.0.0.1'],
            BTU_CLASSROOM_ISSUER_REFERENCE='BTU-UNIVERSITY',
            BTU_AUTHORIZED_COMPLETION_SOURCES=['BTU_GOOGLE_SHEETS', 'BTU_EXCEL'],
            BTU_SPREADSHEET_GOOGLE_SOURCES={'approved': target},
            BTU_GOOGLE_SHEET_ID='', GOOGLE_SERVICE_ACCOUNT_FILE=''))
        create_test_issuer('Synthetic automation acceptance')
        student = Student.objects.create(external_student_id=ROW[0], first_name='Synthetic', last_name='Automation',
            email='synthetic.automation@btu.edu.ge', program='AI', education_level='Bachelor', student_status='ACTIVE')
        Skill.objects.create(skill_code=ROW[2], skill_name='Synthetic automation skill', category='AI',
            description='Synthetic evidence only', stamp_type='FOCUSED', badge_asset_id='synthetic')
        password = secrets.token_urlsafe(32)
        admin = User.objects.create_admin_user(email='synthetic.automation.admin@btu.edu.ge', password=password,
            permission_codenames=['import_completions', 'view_student_records'])
        data = {**definition(), 'google_source': 'approved'}
        profile = provision_profile({'key': 'synthetic-auto-awards', 'version': 1, 'source': 'BTU_GOOGLE_SHEETS',
            'kind': 'SKILL_AWARD', 'definition': data, 'approval_reference': 'SYNTHETIC-INSTITUTIONAL-POLICY'})
        profile.enabled = True
        profile.save(update_fields=['enabled'])
        source = directory / 'synthetic-source.json'
        source.write_text(json.dumps(grid([*ROW[:4], 'PENDING'])))
        # Provider boundary is synthetic; React, API, policy, worker and DB are real.
        def read(_profile):
            rows = json.loads(source.read_text())
            return copy.deepcopy(rows), digest({'target': target, 'rows': rows})
        owned.enter_context(patch('apps.integrations.spreadsheet_automation.read_profile_sheet', side_effect=read))
        owned.enter_context(patch('apps.integrations.importers.preview.read_profile_sheet', side_effect=read))
        owned.enter_context(patch('apps.integrations.spreadsheet_views.read_profile_sheet', side_effect=read))
        stop = threading.Event()
        worker_errors = []
        def worker():
            try:
                while not stop.wait(.1):
                    # Make each opted-in source due quickly for this synthetic acceptance;
                    # production scheduling remains the saved 60+ second interval.
                    from django.utils import timezone
                    SpreadsheetAutomation.objects.filter(enabled=True, lease_token__isnull=True).update(next_poll_at=timezone.now())
                    poll_due_sources(limit=1)
            except Exception as exc:
                worker_errors.append(type(exc).__name__)
            finally:
                connections.close_all()
        ctx = contextvars.copy_context()
        wt = threading.Thread(target=lambda: ctx.run(worker), daemon=True)
        wt.start()
        def stop_worker():
            stop.set()
            wt.join(timeout=30)
            if wt.is_alive():
                raise RuntimeError('Owned automation worker did not stop')
        owned.callback(stop_worker)
        def serve():
            try:
                server.serve_forever()
            finally:
                connections.close_all()
        server = make_server('127.0.0.1', 0, get_wsgi_application(), handler_class=Quiet)
        http_context = contextvars.copy_context()
        thread = threading.Thread(target=lambda: http_context.run(serve), daemon=True)
        thread.start()
        owned.server(server, thread)
        fixture = {'synthetic': True, 'adminEmail': admin.email, 'adminPassword': password,
            'profileId': str(profile.pk), 'sourceFile': str(source), 'row': ROW}
        env = {**os.environ, 'BTU_AUTOMATION_FIXTURE': json.dumps(fixture),
            'BTU_DEV_API_TARGET': f'http://127.0.0.1:{server.server_port}',
            'BTU_TEST_VITE_CACHE': str(directory / 'vite-cache'), 'VITE_ENABLE_DEMO': 'false'}
        result = owned.command(['node', 'scripts/check-spreadsheet-automation.mjs'], cwd=ROOT / 'frontend', env=env)
        stop_worker()
        close_old_connections()
        assert not worker_errors, worker_errors
        assert result.returncode == 0, 'Real Chrome automation acceptance failed'
        assert not SpreadsheetAutomation.objects.get(profile=profile).enabled
        assert Credential.objects.filter(student=student).count() == 3
        assert SpreadsheetAward.objects.filter(actor=admin).count() == 3
        passport = DigitalPassport.objects.get(student=student)
        assert passport.first_issued_at
        assert PassportVersion.objects.filter(passport=passport).count() == 3
        assert SpreadsheetPoll.objects.filter(state='EXCLUDED').exists()
        assert SpreadsheetPoll.objects.filter(state='COMPLETED').count() == 2
        print('PASS owned PG: automatic confirmed discovery, pending/rejected/invalid exclusion, immutable replay, disabled manual path, one permanent Passport and three preserved versions.', flush=True)
        connections.close_all()


if __name__ == '__main__':
    main()
