"""Real Chrome/React/Django acceptance, with owned PG and synthetic awarded skills.

Uses the existing API test settings, not production .env. No Google credentials,
RPC, Anvil, proof overrides or blockchain configuration changes are needed.
"""
import contextvars
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sys
import threading
from wsgiref.simple_server import make_server, WSGIRequestHandler

from disposable_tests import DisposableRun, test_database_name

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'apps.integrations.postgres_test_settings'
os.environ['INTEGRATION_TEST_DB_NAME'] = test_database_name('frontend_django')
import django
django.setup()
from django.conf import settings
from django.core.mail.backends.locmem import EmailBackend
from django.core.wsgi import get_wsgi_application
from django.db import connections
from django.test import override_settings
from openpyxl import Workbook
from apps.accounts.models import User
from apps.credentials.models import Credential
from apps.credentials.test_support import create_test_issuer
from apps.integrations.importers.profiles import provision_profile
from apps.integrations.models import ImportRun, SpreadsheetAward
from apps.integrations.test_spreadsheet_mapping import definition
from apps.passports.models import DigitalPassport, PassportDocument
from apps.skills.models import Skill, VerifiedAchievement
from apps.students.models import Student


class Quiet(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def main():
    if not os.environ.get('BTU_BROWSER_TOOLS'):
        raise RuntimeError('Provide the existing isolated Playwright installation using BTU_BROWSER_TOOLS.')
    with DisposableRun() as owned:
        owned.database()
        directory = Path(settings.MEDIA_ROOT)

        class TestMailbox(EmailBackend):
            def send_messages(self, messages):
                count = super().send_messages(messages)
                for message in messages:
                    code = re.search(r'code is: ([0-9]{6})', message.body)
                    if code:
                        (directory / 'student.otp').write_text(code[1])
                return count

        owned.enter_context(override_settings(ROOT_URLCONF='config.urls', ALLOWED_HOSTS=['127.0.0.1'],
            EMAIL_BACKEND='__main__.TestMailbox',
            BTU_CLASSROOM_ISSUER_REFERENCE='BTU-UNIVERSITY',
            BTU_AUTHORIZED_COMPLETION_SOURCES=['BTU_EXCEL', 'BTU_GOOGLE_SHEETS'],
            BTU_GOOGLE_SHEET_ID='', GOOGLE_SERVICE_ACCOUNT_FILE='',
            BTU_SPREADSHEET_GOOGLE_SOURCES={'synthetic-google': {
                'spreadsheet_id': 'SYNTHETIC_NO_GOOGLE_ACCESS', 'worksheet': 'Passport Skill Records'}},
            PASSPORT_PDF_REQUESTS_PER_MINUTE=1000))
        # Django resolves the backend via an importable module attribute.
        globals()['TestMailbox'] = TestMailbox
        create_test_issuer('Synthetic BTU integration')
        student = Student.objects.create(external_student_id='SYNTHETIC-STUDENT', first_name='Synthetic',
            last_name='Integration Student', email='synthetic.integration@btu.edu.ge', program='AI',
            education_level='Bachelor', student_status='ACTIVE')
        Skill.objects.create(skill_code='SYNTHETIC-SKILL', skill_name='Synthetic integration skill',
            category='AI', description='Synthetic awarded-skill evidence', stamp_type='FOCUSED', badge_asset_id='synthetic')
        password = secrets.token_urlsafe(32)
        admin = User.objects.create_admin_user(email='synthetic.integration.admin@btu.edu.ge', password=password,
            permission_codenames=['view_student_records', 'import_completions'])
        data = definition()
        data['columns']['approval_status'] = ['Institutional Approval']
        profile = provision_profile({'key': 'synthetic-btu-awards', 'version': 1, 'source': 'BTU_EXCEL',
            'kind': 'SKILL_AWARD', 'definition': data, 'approval_reference': 'SYNTHETIC-INTEGRATION-TEST-ONLY'})
        google = provision_profile({'key': 'synthetic-google-unconfigured', 'version': 1, 'source': 'BTU_GOOGLE_SHEETS',
            'kind': 'SKILL_AWARD', 'definition': {**data, 'google_source': 'synthetic-google'},
            'approval_reference': 'SYNTHETIC-NO-GOOGLE-TEST'})
        official_definition = {**data, 'columns': {k: v for k, v in data['columns'].items() if k != 'approval_status'}}
        official = provision_profile({'key': 'synthetic-btu-original-format', 'version': 1, 'source': 'BTU_EXCEL',
            'kind': 'SKILL_AWARD', 'definition': official_definition, 'approval_reference': 'SYNTHETIC-REVIEW-ONLY'})
        for item in (profile, google, official):
            item.enabled = True
            item.save(update_fields=['enabled'])
        headers = ['Student ID', 'First Name', 'Last Name', 'BTU Email (Test)', 'Program', 'Education Level',
            'Passport ID (Existing)', 'First Issued (Existing)', 'Student Status', 'Record ID', 'Skill ID',
            'Skill Name', 'Skill Category', 'Badge/Stamp Code', 'Skill Description', 'Date Earned',
            'Passport Sync Status', 'Synced Passport Version', 'Synced At (UTC)', 'Sync Error / Notes']
        values = [student.external_student_id, 'Synthetic', 'Integration Student', student.email, 'AI', 'Bachelor',
            '', '', 'ACTIVE', 'SYNTHETIC-RECORD', 'SYNTHETIC-SKILL', 'Synthetic integration skill', 'AI',
            'synthetic', 'Synthetic awarded-skill evidence', '2026-01-01', 'CONFIRMED', '', '', 'Synthetic output only']
        book = Workbook()
        sheet = book.active
        sheet.title = 'Passport Skill Records'
        sheet.append(['Synthetic copy of the original header format']); sheet.append([]); sheet.append([])
        sheet.append(headers); sheet.append(values)
        original_format = directory / 'synthetic-btu-original-format.xlsx'
        book.save(original_format); book.close()
        book = Workbook()
        sheet = book.active
        sheet.title = 'Passport Skill Records'
        sheet.append(['Synthetic independently approved awards']); sheet.append([]); sheet.append([])
        sheet.append([*headers, 'Institutional Approval'])
        valid = [*values, 'CONFIRMED']
        sheet.append(valid); sheet.append(valid)
        for state in ('PENDING', 'REJECTED'):
            row = list(valid); row[9] = 'SYNTHETIC-' + state; row[20] = state; sheet.append(row)
        for event, column, value in [('UNKNOWN-STUDENT', 0, 'SYNTHETIC-UNKNOWN'),
                                      ('UNKNOWN-SKILL', 10, 'SYNTHETIC-UNAPPROVED'), ('FORMULA', 0, '=1+1')]:
            row = list(valid); row[9] = 'SYNTHETIC-' + event; row[column] = value; sheet.append(row)
        workbook = directory / 'synthetic-btu-awards.xlsx'
        book.save(workbook); book.close()
        original_hash = hashlib.sha256(workbook.read_bytes()).hexdigest()
        metadata = {'synthetic': True, 'adminEmail': admin.email, 'adminPassword': password,
            'studentEmail': student.email, 'studentName': 'Synthetic Integration Student',
            'studentId': str(student.pk), 'profileId': str(profile.pk), 'googleProfileId': str(google.pk),
            'officialProfileId': str(official.pk), 'originalFormatWorkbook': str(original_format),
            'workbook': str(workbook), 'mailbox': str(directory / 'student.otp')}
        def serve():
            try:
                server.serve_forever()
            finally:
                connections.close_all()
        server = make_server('127.0.0.1', 0, get_wsgi_application(), handler_class=Quiet)
        context = contextvars.copy_context()
        thread = threading.Thread(target=lambda: context.run(serve), daemon=True)
        thread.start()
        owned.server(server, thread)
        env = {**os.environ, 'BTU_FRONTEND_DJANGO_FIXTURE': json.dumps(metadata),
            'BTU_DEV_API_TARGET': f'http://127.0.0.1:{server.server_port}',
            'BTU_TEST_VITE_CACHE': str(directory / 'vite-cache'), 'VITE_ENABLE_DEMO': 'false'}
        result = owned.command(['node', 'scripts/check-frontend-django-http.mjs'], cwd=ROOT / 'frontend', env=env)
        if result.returncode:
            raise RuntimeError('Real Chrome/Django acceptance failed. No external Google or blockchain acceptance was attempted.')
        assert VerifiedAchievement.objects.filter(student=student).count() == 1
        assert Credential.objects.filter(student=student).count() == 1
        assert SpreadsheetAward.objects.filter(actor=admin).count() == 1
        assert DigitalPassport.objects.filter(student=student).count() == 1
        assert PassportDocument.objects.filter(passport_version__passport__student=student, status='ISSUED').count() == 1
        assert ImportRun.objects.filter(actor=admin, state='PARTIAL').exists()
        assert hashlib.sha256(workbook.read_bytes()).hexdigest() == original_hash
        connections.close_all()
        print('PASS owned PostgreSQL: one confirmed skill/credential/Passport/PDF, persisted partial history, replay safety and unchanged source workbook.', flush=True)


if __name__ == '__main__':
    main()
