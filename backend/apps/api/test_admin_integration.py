"""Admin browser-support contracts retain the existing exact grant boundaries."""
from django.contrib.auth.models import Group, Permission
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.authorization import ADMIN_CAPABILITIES, admin_capabilities
from apps.accounts.models import User
from apps.accounts.views import _user_summary
from apps.api import tests as fixtures
from apps.integrations.models import ClassroomSyncEvent, ImportRun


class CapabilitySummaryTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_admin_user(email='capabilities@btu.edu.ge', password='Synthetic-Capability-Password!2026', permission_codenames=['view_student_records'])

    def permission(self, name):
        return Permission.objects.get(content_type__app_label='accounts', codename=name)

    def test_login_and_me_publish_only_effective_allowlisted_capabilities(self):
        group = Group.objects.create(name='Synthetic sync operators')
        group.permissions.add(self.permission('sync_classroom'))
        self.admin.groups.add(group)
        # A nonproduct Django grant must never enter the public summary.
        self.admin.user_permissions.add(Permission.objects.get(content_type__app_label='auth', codename='view_group'))
        client = APIClient()
        login = client.post(reverse('accounts:login'), {'email': self.admin.email, 'password': 'Synthetic-Capability-Password!2026'}, format='json')
        self.assertEqual(login.status_code, 200)
        expected = ['view_student_records', 'sync_classroom']
        self.assertEqual(login.data['capabilities'], expected)
        me = client.get(reverse('accounts:current-user'))
        self.assertEqual(me.data['capabilities'], expected)
        self.assertEqual(set(me.data), {'email','role','email_verified','student_association','capabilities'})
        self.admin.groups.clear()
        self.admin.user_permissions.clear()
        self.assertEqual(client.get(reverse('accounts:current-user')).data['capabilities'], [])

    def test_each_grant_is_independent_and_role_or_flags_never_grant_access(self):
        for name in ADMIN_CAPABILITIES:
            self.admin.user_permissions.set([self.permission(name)])
            fresh = User.objects.get(pk=self.admin.pk)
            self.assertEqual(admin_capabilities(fresh), [name])
        for field, value in [('is_active', False), ('is_email_verified', False), ('is_staff', False), ('is_superuser', True), ('role', 'STUDENT')]:
            user = User.objects.get(pk=self.admin.pk)
            setattr(user, field, value)
            self.assertEqual(_user_summary(user)['capabilities'], [])


class AdminReadContracts(TestCase):
    # Reuse the existing canonical synthetic fixture, not its full test methods.
    setUp = fixtures.PrivateAPITests.setUp
    make_student = fixtures.PrivateAPITests.make_student
    make_award = fixtures.PrivateAPITests.make_award
    issue = fixtures.PrivateAPITests.issue
    as_admin = fixtures.PrivateAPITests.as_admin

    def test_permissioned_reads_and_sanitized_projections(self):
        credential = self.issue()
        self.as_admin()
        awards = self.client.get(f'/api/admin/students/{self.student.pk}/achievements/').json()
        self.assertEqual(awards['count'], 1)
        self.assertEqual(awards['results'][0]['credential_count'], 1)
        self.assertNotIn('evidence', str(awards))
        self.assertNotIn('payload', str(awards))
        self.make_award(self.student, status='PENDING')
        self.assertEqual(self.client.get(f'/api/admin/students/{self.student.pk}/achievements/').json()['count'], 1)
        history = self.client.get(f'/api/admin/credentials/{credential.pk}/history/').json()['results']
        self.assertEqual(set(history[0]), {'id','event_type','occurred_at'})
        self.assertEqual(history[0]['event_type'], 'ISSUED')
        self.assertEqual(self.client.get('/api/admin/catalog/').json()['count'], 1)
        mappings = self.client.get('/api/admin/course-mappings/').json()
        self.assertEqual(mappings['source'], 'BACKEND_CONTROLLED_COURSE_MAPPINGS')
        self.assertEqual(mappings['results'][0]['course_id'], 'AI-101')
        self.assertEqual(self.client.post('/api/admin/course-mappings/', {}, format='json').status_code, 405)

    def test_read_grant_does_not_allow_writes_and_write_grant_does_not_allow_reads(self):
        for name in ('view_student_records', 'manage_credentials', 'manage_student_accounts', 'revoke_credentials', 'sync_classroom', 'import_completions'):
            self.admin.user_permissions.set(Permission.objects.filter(content_type__app_label='accounts', codename=name))
            self.as_admin()
            for path in ['/api/admin/catalog/', '/api/admin/course-mappings/', f'/api/admin/students/{self.student.pk}/achievements/']:
                self.assertEqual(self.client.get(path).status_code, 200 if name == 'view_student_records' else 403)
            if name == 'view_student_records':
                self.assertEqual(self.client.post('/api/admin/credentials/issue/', {}, format='json').status_code, 403)
                self.assertEqual(self.client.patch(f'/api/admin/students/{self.student.pk}/', {'program': 'Changed'}, format='json').status_code, 403)

    def test_student_and_anonymous_denied_new_admin_reads(self):
        for user in (self.user, None):
            self.client.force_authenticate(user)
            for path in ['/api/admin/catalog/', '/api/admin/course-mappings/', f'/api/admin/students/{self.student.pk}/achievements/']:
                self.assertEqual(self.client.get(path).status_code, 403)

    def test_import_event_identifiers_require_import_grant_and_exclude_payload(self):
        run = ImportRun.objects.create(source='BTU_EXCEL')
        event = ClassroomSyncEvent.objects.create(source='BTU_EXCEL', source_event_id='READ-ONLY-EVENT', payload={'secret': 'private-source-payload'}, payload_sha256='c'*64)
        run.events.add(event)
        url = f'/api/integrations/imports/{run.pk}/events/'
        self.as_admin()
        self.assertEqual(self.client.get(url).status_code, 403)
        self.admin.user_permissions.set(Permission.objects.filter(content_type__app_label='accounts', codename='import_completions'))
        self.as_admin()
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['results'][0]['id'], str(event.pk))
        self.assertNotIn('payload', str(response.data))
        self.assertEqual(self.client.get(url, {'cursor': 'bad'}).status_code, 404)
        self.assertEqual(self.client.get('/api/integrations/imports/999999/events/').status_code, 404)
