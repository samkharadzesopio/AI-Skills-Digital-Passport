"""Socket-level session/CSRF/preview/confirmation acceptance; owned fixtures only."""
import contextvars
import os
import secrets
import sys
import threading
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server

from disposable_tests import DisposableRun, test_database_name

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'apps.integrations.postgres_test_settings'
os.environ['INTEGRATION_TEST_DB_NAME'] = test_database_name('spreadsheet_http')
import django
django.setup()
import requests
from django.core.wsgi import get_wsgi_application
from django.db import connections
from django.test import override_settings
from apps.accounts.models import User
from apps.credentials.models import Credential
from apps.credentials.test_support import create_test_issuer
from apps.integrations.importers.profiles import provision_profile
from apps.integrations.models import SpreadsheetAward
from apps.integrations.test_spreadsheet_mapping import definition, grid, ROW, workbook
from apps.skills.models import Skill
from apps.students.models import Student


class Quiet(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def main():
    with DisposableRun() as owned:
        owned.database()
        owned.enter_context(override_settings(ROOT_URLCONF='config.urls', ALLOWED_HOSTS=['127.0.0.1'],
            BTU_CLASSROOM_ISSUER_REFERENCE='BTU-UNIVERSITY', BTU_AUTHORIZED_COMPLETION_SOURCES=['BTU_EXCEL']))
        create_test_issuer('Synthetic BTU')
        Student.objects.create(external_student_id=ROW[0], first_name='Synthetic', last_name='Student',
            email='http-spreadsheet@btu.edu.ge', program='AI', education_level='Bachelor', student_status='ACTIVE')
        Skill.objects.create(skill_code=ROW[2], skill_name='Synthetic skill', category='AI Skill',
            description='Synthetic', stamp_type='FOCUSED', badge_asset_id='synthetic')
        password = secrets.token_urlsafe(32)
        User.objects.create_admin_user(email='http-import@btu.edu.ge', password=password, permission_codenames=['import_completions'])
        profile = provision_profile({'key': 'http-synthetic', 'version': 1, 'source': 'BTU_EXCEL', 'kind': 'SKILL_AWARD',
            'definition': definition(), 'approval_reference': 'SYNTHETIC-REVIEWED-POLICY'})
        profile.enabled = True
        profile.save(update_fields=['enabled'])
        server = make_server('127.0.0.1', 0, get_wsgi_application(), handler_class=Quiet)
        context = contextvars.copy_context()
        thread = threading.Thread(target=lambda: context.run(server.serve_forever), daemon=True)
        thread.start()
        owned.server(server, thread)
        base = f'http://127.0.0.1:{server.server_port}'
        client = requests.Session()
        client.trust_env = False
        owned.callback(client.close)
        count = 0

        def request(method, path, expected=200, csrf=True, **kwargs):
            nonlocal count
            headers = {'X-CSRFToken': client.cookies.get('csrftoken', '')} if csrf and method != 'GET' else {}
            response = client.request(method, base + path, headers=headers, timeout=20, **kwargs)
            count += 1
            assert response.status_code == expected, (path, response.status_code, expected)
            if '/api/integrations/' in path:
                assert 'no-store' in response.headers.get('Cache-Control', '')
            return response

        request('GET', '/api/integrations/import/profiles/', expected=403)
        request('GET', '/api/accounts/csrf/')
        request('POST', '/api/accounts/login/', json={'email': 'http-import@btu.edu.ge', 'password': password})
        assert request('GET', '/api/accounts/me/').json()['capabilities'] == ['import_completions']
        request('GET', '/api/integrations/import/profiles/')
        upload = workbook(grid(ROW)).getvalue()
        preview = request('POST', '/api/integrations/import/excel/preview/', expected=201,
            data={'profile_id': str(profile.pk)}, files={'file': ('synthetic.xlsx', upload)}).json()
        assert preview['report']['valid_records'] == 1 and Credential.objects.count() == 0
        assert ROW[0] not in str(preview)
        path = f"/api/integrations/import/previews/{preview['id']}/"
        request('GET', path)
        body = {'confirm': True, 'snapshot_sha256': preview['snapshot_sha256']}
        request('POST', path + 'confirm/', expected=403, csrf=False, json=body)
        request('POST', path + 'confirm/', expected=409, json={**body, 'snapshot_sha256': '0' * 64})
        assert request('POST', path + 'confirm/', json=body).json()['result']['issued'] == 1
        request('POST', path + 'confirm/', json=body)
        assert Credential.objects.count() == SpreadsheetAward.objects.count() == 1
        request('POST', '/api/accounts/logout/', expected=204, json={})
        request('GET', path, expected=403)
        connections.close_all()
        print(f'PASS spreadsheet HTTP acceptance: {count} real requests; session, CSRF, private preview, confirmation, replay and logout.')


if __name__ == '__main__':
    main()
