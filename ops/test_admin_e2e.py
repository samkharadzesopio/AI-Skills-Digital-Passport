"""Real Admin -> Student -> public UI acceptance; disposable loopback PG only.

Application responses, permissions and domain services are never mocked. Classroom
reads its existing controlled simulation; spreadsheets use actual uploaded bytes.
"""
import contextvars
from datetime import date
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
from wsgiref.simple_server import make_server, WSGIRequestHandler, WSGIServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'apps.integrations.postgres_test_settings'
os.environ['INTEGRATION_TEST_DB_NAME'] = 'test_admin_frontend_e2e'
import django
django.setup()
from django.conf import settings
from django.core.mail.backends.locmem import EmailBackend
from django.core.wsgi import get_wsgi_application
from django.db import connections
from django.test.utils import setup_databases, teardown_databases
from openpyxl import Workbook
from apps.accounts.models import User
from apps.credentials.models import Credential
from apps.credentials.test_support import create_test_issuer
from apps.integrations.models import ClassroomSyncEvent, ImportRun
from apps.passports.models import PassportDocument
from apps.skills.models import Skill, VerifiedAchievement
from apps.students.models import Student

settings.ROOT_URLCONF = 'config.urls'
settings.ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
settings.CREDENTIAL_REVOCATION_AUTHORIZER = 'apps.accounts.authorization.authorize_credential_revocation'
settings.BTU_CLASSROOM_ISSUER_REFERENCE = 'BTU-UNIVERSITY'
settings.BTU_AUTHORIZED_COMPLETION_SOURCES = ['BTU_EXCEL']
settings.BTU_GOOGLE_SHEET_ID = None
settings.PASSPORT_PDF_REQUESTS_PER_MINUTE = 1000


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


class IsolatedServer(WSGIServer):
    allow_reuse_address = False


db = setup_databases(verbosity=0, interactive=False)
server = None
try:
    with tempfile.TemporaryDirectory(prefix='admin-ui-http-') as directory:
        artifact = Path(directory)
        settings.MEDIA_ROOT = str(artifact / 'documents')

        class TestMailbox(EmailBackend):
            def send_messages(self, messages):
                result = super().send_messages(messages)
                for message in messages:
                    match = re.search(r'code is: ([0-9]{6})', message.body)
                    if match:
                        for recipient in message.to:
                            (artifact / (recipient.replace('@', '_') + '.otp')).write_text(match.group(1))
                return result

        settings.EMAIL_BACKEND = '__main__.TestMailbox'
        student = Student.objects.create(external_student_id='BTU-T-0010', first_name='Synthetic', last_name='Admin Workflow', email='admin-journey-student@btu.edu.ge', program='Computing', education_level='Bachelor', student_status='ACTIVE')
        User.objects.create_user(email=student.email, student=student, is_email_verified=True)
        full = User.objects.create_admin_user(email='journey-admin@btu.edu.ge', password='Synthetic-Admin-Journey!2026', permission_codenames=['view_student_records','manage_student_accounts','manage_credentials','revoke_credentials','sync_classroom','import_completions'])
        User.objects.create_admin_user(email='journey-reader@btu.edu.ge', password='Synthetic-Reader-Journey!2026', permission_codenames=['view_student_records'])
        create_test_issuer('Business and Technology University')
        for code in ['AI_LITERACY','AI_FUNDAMENTALS','MACHINE_LEARNING','DATA_ANALYSIS','GENERATIVE_AI','PROMPT_ENGINEERING']:
            Skill.objects.create(skill_code=code, skill_name=code.replace('_', ' ').title(), category='Artificial Intelligence', subcategory='Learning evidence', description='Synthetic approved completion skill.', stamp_type='APPLIED', badge_asset_id='ai_applied.png')
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(['external_student_id','course_id','completion_status','grade','passed','completion_date','source_event_id'])
        sheet.append([student.external_student_id,'AI-201','completed',94,True,date(2026,10,1),'ADMIN-HTTP-EXCEL-001'])
        sheet.append([student.external_student_id,'AI-201','completed',94,False,date(2026,10,1),'ADMIN-HTTP-EXCEL-BAD'])
        workbook.save(artifact / 'completion-evidence.xlsx')
        workbook.close()
        # A durably received, unprocessed approved import can be recovered using
        # the exact existing retry API, without replacing or inventing payloads.
        from apps.integrations.classroom_automation import receive
        replay = receive({'source':'BTU_EXCEL','event_id':'ADMIN-HTTP-RECOVERY','student_id':student.external_student_id,'course_id':'AI-301','completion_status':'completed','grade':90,'passed':True,'completion_date':'2026-10-01'}, source='BTU_EXCEL', actor=full)
        ClassroomSyncEvent.objects.filter(pk=replay).update(state='FAILED', retryable=True, attempts=1, error_code='TemporaryFailure')
        run = ImportRun.objects.create(source='BTU_EXCEL', actor=full, state='FAILED')
        run.events.add(replay)
        metadata = {'studentId':str(student.pk), 'email':student.email, 'recoveryRun':run.pk, 'recoveryEvent':str(replay)}
        server = make_server('127.0.0.1', 0, get_wsgi_application(), server_class=IsolatedServer, handler_class=QuietHandler)
        context = contextvars.copy_context()
        threading.Thread(target=lambda: context.run(server.serve_forever), daemon=True).start()
        env = {**os.environ, 'BTU_DEV_API_TARGET': f'http://127.0.0.1:{server.server_port}', 'BTU_ADMIN_FIXTURE':json.dumps(metadata), 'BTU_ADMIN_ARTIFACTS':directory, 'VITE_ENABLE_DEMO':'false', 'VITE_PUBLIC_VERIFICATION_ENABLED':'true'}
        result = subprocess.run(['node','scripts/check-admin-http.mjs'], cwd=ROOT/'frontend', env=env, timeout=240)
        if result.returncode:
            raise RuntimeError(f'Admin HTTP acceptance failed with exit {result.returncode}')
        assert VerifiedAchievement.objects.filter(student=student).count() == 6
        assert Credential.objects.filter(student=student).count() == 4, 'One sync, one explicit issuance, one Excel, one recovered event; no replay duplicates'
        assert Credential.objects.filter(student=student, status='REVOKED').count() == 1
        assert PassportDocument.objects.filter(status='ISSUED').count() == 1
        assert ImportRun.objects.filter(validation_errors__contains=[{'row':3,'code':'INVALID_ROW'}]).exists()
        assert ClassroomSyncEvent.objects.get(pk=replay).state == 'CREDENTIAL_ISSUED'
        assert ImportRun.objects.get(pk=run.pk).state == 'COMPLETED'
        print('PASS PostgreSQL: six verified achievements, four intended credentials, one revocation, one registered PDF, persisted row error and recovered import; no replay duplicates.', flush=True)
finally:
    if server:
        server.shutdown()
        server.server_close()
    connections.close_all()
    teardown_databases(db, verbosity=0)
