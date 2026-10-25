from datetime import date, timedelta
from uuid import uuid4
from django.contrib.auth.models import Permission
from django.db import connection, IntegrityError, transaction
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient
from apps.accounts.models import User, SecurityAudit
from apps.credentials.models import Credential, CredentialPassportRefresh
from apps.credentials.services import issue_credential, revoke_credential
from apps.credentials.test_support import create_test_issuer
from apps.skills.models import Skill, VerifiedAchievement, AchievementSourceEvent
from apps.students.models import Student
from apps.passports.models import DigitalPassport, PassportVersion, PassportVersionSkill
from apps.passports.document_services import _render_context, _version_queryset


@override_settings(CREDENTIAL_REVOCATION_AUTHORIZER='apps.accounts.authorization.authorize_credential_revocation', VERIFICATION_TRUSTED_ISSUER_REFERENCES=['BTU-UNIVERSITY'])
class PrivateAPITests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.student = self.make_student('one')
        self.other = self.make_student('two')
        self.user = User.objects.create_user(email=self.student.email, student=self.student, role='STUDENT', is_email_verified=True)
        self.admin = User.objects.create_admin_user(email='api-admin@btu.edu.ge', password='SyntheticAdminPassword!193', permission_codenames=['view_student_records', 'manage_student_accounts', 'manage_credentials', 'revoke_credentials'])
        self.admin.user_permissions.set(Permission.objects.filter(content_type__app_label='accounts', codename__in=['view_student_records', 'manage_student_accounts', 'manage_credentials', 'revoke_credentials']))
        self.skill = Skill.objects.create(skill_code='API-AI', skill_name='AI reasoning', category='AI', subcategory='Reasoning', description='Verified reasoning', stamp_type='APPLIED', badge_asset_id='reasoning')
        self.award = self.make_award(self.student)
        self.other_award = self.make_award(self.other)
        create_test_issuer('Business and Technology University')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def make_student(self, suffix):
        return Student.objects.create(external_student_id='API-'+suffix, first_name='Synthetic', last_name=suffix, email=suffix+'@btu.edu.ge', program='CS', education_level='Bachelor', student_status='ACTIVE')

    def make_award(self, student, skill=None, status='VERIFIED'):
        event = AchievementSourceEvent.objects.create(source='API_TEST', source_event_id=str(uuid4()), course_id='COURSE-1', evidence={'private': 'do not expose'}, payload_sha256='a'*64)
        return VerifiedAchievement.objects.create(student=student, skill=skill or self.skill, source_event=event, earned_on=date.today(), verification_status=status)

    def issue(self, award=None, **kwargs):
        return issue_credential(issuer_reference='BTU-UNIVERSITY', idempotency_key=str(uuid4()), achievement_ids=[(award or self.award).pk], **kwargs)

    def as_admin(self):
        self.client.force_authenticate(User.objects.get(pk=self.admin.pk))

    def test_student_all_routes_require_authentication(self):
        self.client.force_authenticate(None)
        for route in ['dashboard/', 'skills/', 'achievements/', 'credentials/', 'passport/', 'passport/versions/', f'credentials/{uuid4()}/', f'passport/versions/{uuid4()}/']:
            self.assertEqual(self.client.get('/api/student/'+route).status_code, 403, route)

    def test_student_dashboard_empty_credentials_and_passport(self):
        data = self.client.get('/api/student/dashboard/').json()
        self.assertEqual(data['recognized_skills'], 1)
        self.assertEqual(data['verified_achievements'], 1)
        self.assertEqual(data['credentials']['total'], 0)
        self.assertIsNone(data['passport'])
        self.assertEqual(data['skills_by_subcategory'], [{'subcategory': 'Reasoning', 'count': 1}])
        self.assertEqual(self.client.get('/api/student/passport/').json(), {'passport': None})
        self.assertEqual(self.client.get('/api/student/passport/versions/').json()['count'], 0)

    def test_completely_empty_student(self):
        empty = self.make_student('empty')
        user = User.objects.create_user(email=empty.email, student=empty, role='STUDENT', is_email_verified=True)
        self.client.force_authenticate(user)
        data = self.client.get('/api/student/dashboard/').json()
        self.assertEqual(data['recognized_skills'], 0)
        self.assertEqual(data['verified_achievements'], 0)
        self.assertEqual(data['skills_by_category'], [])

    def test_skills_and_achievements_preserve_classification_without_private_source_data(self):
        self.make_award(self.student, status='PENDING')
        self.make_award(self.student, status='REJECTED')
        skills = self.client.get('/api/student/skills/').json()
        self.assertEqual(skills['count'], 1)
        skill = skills['results'][0]
        self.assertEqual((skill['category'], skill['subcategory'], skill['competency_level']), ('AI', 'Reasoning', 'APPLIED'))
        self.assertEqual(len(skill['achievements']), 1)
        awards = self.client.get('/api/student/achievements/').json()
        self.assertEqual(awards['count'], 1)
        self.assertEqual(awards['results'][0]['course_reference'], 'COURSE-1')
        self.assertNotIn('private', str(awards))

    def test_student_cannot_access_foreign_credential_or_version(self):
        with self.captureOnCommitCallbacks(execute=True):
            foreign = self.issue(self.other_award)
        passport = DigitalPassport.objects.get(student=self.other)
        for route in [f'credentials/{foreign.pk}/', f'passport/versions/{passport.latest_version_id}/']:
            self.assertEqual(self.client.get('/api/student/'+route).status_code, 404)
        self.assertEqual(self.client.get('/api/student/credentials/', {'student_id': str(self.other.pk)}).json()['count'], 0)

    def test_credential_statuses_and_dashboard_counts(self):
        self.issue()
        expired = self.issue(issued_at=self.now-timedelta(days=3), expires_at=self.now-timedelta(days=1))
        revoked = self.issue()
        revoke_credential(public_reference=revoked.public_reference, actor=self.admin, reason='Invalid award')
        future = self.issue(issued_at=self.now+timedelta(days=1))
        rows = self.client.get('/api/student/credentials/').json()['results']
        self.assertEqual({row['validity_status'] for row in rows}, {'VALID', 'EXPIRED', 'REVOKED', 'INVALID'})
        counts = self.client.get('/api/student/dashboard/').json()['credentials']
        self.assertEqual(counts, {'total': 4, 'valid': 1, 'expired': 1, 'revoked': 1, 'invalid': 1})
        for credential, status in [(expired, 'EXPIRED'), (revoked, 'REVOKED'), (future, 'INVALID')]:
            self.assertEqual(self.client.get(f'/api/student/credentials/{credential.pk}/').json()['validity_status'], status)

    def test_student_api_is_read_only(self):
        for route in ['dashboard/', 'skills/', 'achievements/', 'credentials/', 'passport/', 'passport/versions/']:
            self.assertEqual(self.client.post('/api/student/'+route, {}, format='json').status_code, 405)

    def test_unlinked_inactive_unverified_and_mismatched_student_rejected(self):
        for values in [{'student': None}, {'is_email_verified': False}, {'is_active': False}]:
            user = User.objects.get(pk=self.user.pk)
            for key, value in values.items(): setattr(user, key, value)
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get('/api/student/dashboard/').status_code, 403)
        self.student.student_status = 'INACTIVE'; self.student.save()
        self.client.force_authenticate(User.objects.get(pk=self.user.pk))
        self.assertEqual(self.client.get('/api/student/dashboard/').status_code, 403)

    def test_admin_routes_deny_students(self):
        for route in ['students/', f'students/{self.student.pk}/', 'credentials/', 'passports/', 'statistics/']:
            self.assertEqual(self.client.get('/api/admin/'+route).status_code, 403)
        for route in ['students/', 'credentials/issue/', f'credentials/{uuid4()}/revoke/']:
            self.assertEqual(self.client.post('/api/admin/'+route, {}, format='json').status_code, 403)

    def test_admin_requires_exact_permission(self):
        self.admin.user_permissions.clear(); self.as_admin()
        self.assertEqual(self.client.get('/api/admin/students/').status_code, 403)
        self.admin.user_permissions.add(Permission.objects.get(content_type__app_label='accounts', codename='view_student_records'))
        self.as_admin()
        self.assertEqual(self.client.get('/api/admin/students/').status_code, 200)
        self.assertEqual(self.client.post('/api/admin/students/', {}, format='json').status_code, 403)
        self.assertEqual(self.client.post('/api/admin/credentials/issue/', {}, format='json').status_code, 403)
        self.assertEqual(self.client.post(f'/api/admin/credentials/{uuid4()}/revoke/', {}, format='json').status_code, 403)

    def test_admin_create_validate_update_and_audit(self):
        self.as_admin()
        payload = dict(external_student_id='API-new', first_name='New', last_name='Student', email='new@btu.edu.ge', program='CS', education_level='Bachelor', student_status='ACTIVE')
        response = self.client.post('/api/admin/students/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        id = response.data['id']
        self.assertEqual(self.client.post('/api/admin/students/', payload, format='json').status_code, 400)
        response = self.client.patch(f'/api/admin/students/{id}/', {'program': 'AI'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        for field in ['external_student_id', 'email', 'first_name', 'last_name', 'user', 'student_id', 'id']:
            self.assertEqual(self.client.patch(f'/api/admin/students/{id}/', {field: str(uuid4())}, format='json').status_code, 400, field)
        self.assertTrue(SecurityAudit.objects.filter(actor=self.admin, status_code=201).exists())
        self.assertTrue(SecurityAudit.objects.filter(actor=self.admin, status_code=400).exists())

    def test_student_create_rejects_empty_and_case_insensitive_duplicate_email(self):
        self.as_admin()
        payload = dict(external_student_id='new', first_name='New', last_name='Student', email=self.student.email.upper(), program='CS', education_level='Bachelor', student_status='ACTIVE')
        self.assertEqual(self.client.post('/api/admin/students/', payload, format='json').status_code, 400)
        payload['email'] = 'new@btu.edu.ge'; payload['program'] = '  '
        self.assertEqual(self.client.post('/api/admin/students/', payload, format='json').status_code, 400)

    def test_admin_students_filter_pagination_and_detail(self):
        self.as_admin()
        response = self.client.get('/api/admin/students/', {'page_size': 1}).json()
        self.assertEqual(response['count'], 2); self.assertEqual(len(response['results']), 1)
        self.assertIsNotNone(response['next'])
        self.assertEqual(self.client.get('/api/admin/students/', {'search': 'API-one', 'program': 'CS', 'student_status': 'ACTIVE'}).json()['count'], 1)
        self.assertEqual(self.client.get(f'/api/admin/students/{self.student.pk}/').json()['profile']['id'], str(self.student.pk))
        self.assertEqual(self.client.get('/api/admin/students/', {'page': 999}).status_code, 404)

    def test_admin_issuance_and_revocation_refresh_passport_and_public_verification(self):
        self.as_admin()
        payload = {'idempotency_key': 'API-issue', 'achievement_ids': [str(self.award.pk)]}
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post('/api/admin/credentials/issue/', payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        credential_id = response.data['id']
        passport = DigitalPassport.objects.get(student=self.student)
        first_version = passport.latest_version
        self.assertEqual(first_version.skill_snapshots.get().subcategory, 'Reasoning')
        replay = self.client.post('/api/admin/credentials/issue/', payload, format='json')
        self.assertEqual(replay.data['id'], credential_id)
        self.assertEqual(Credential.objects.count(), 1)
        changed = {**payload, 'achievement_ids': [str(self.other_award.pk)]}
        self.assertEqual(self.client.post('/api/admin/credentials/issue/', changed, format='json').status_code, 409)
        Skill.objects.filter(pk=self.skill.pk).update(subcategory='Changed')
        with self.captureOnCommitCallbacks(execute=True):
            revoked = self.client.post(f'/api/admin/credentials/{credential_id}/revoke/', {'reason': 'Revoked by institution'}, format='json')
        self.assertEqual(revoked.status_code, 200, revoked.data)
        self.assertEqual(revoked.data['validity_status'], 'REVOKED')
        passport.refresh_from_db()
        self.assertNotEqual(first_version.pk, passport.latest_version_id)
        self.assertEqual(passport.latest_version.skill_snapshots.count(), 0)
        self.assertEqual(first_version.skill_snapshots.get().subcategory, 'Reasoning')
        self.assertEqual(CredentialPassportRefresh.objects.filter(status='COMPLETED').count(), 2)
        public = APIClient().get(f'/api/verification/{response.data["public_reference"]}/')
        self.assertEqual(public.status_code, 200)
        self.assertIn('REVOKED', str(public.data).upper())
        self.client.force_authenticate(self.user)
        history = self.client.get('/api/student/passport/versions/').json()
        self.assertEqual(history['count'], 2)
        old = self.client.get(f'/api/student/passport/versions/{first_version.pk}/').json()
        self.assertEqual(old['skills'][0]['subcategory'], 'Reasoning')

    def test_issue_validates_verified_awards_and_fixed_issuer(self):
        self.as_admin()
        pending = self.make_award(self.student, status='PENDING')
        for ids in [[], [str(uuid4())], [str(pending.pk)], [str(self.award.pk), str(self.other_award.pk)], [str(self.award.pk)]*2]:
            response = self.client.post('/api/admin/credentials/issue/', {'idempotency_key': str(uuid4()), 'achievement_ids': ids}, format='json')
            self.assertEqual(response.status_code, 400, response.data)
        response = self.client.post('/api/admin/credentials/issue/', {'idempotency_key': 'fixed', 'achievement_ids': [str(self.award.pk)], 'issuer_reference': 'OTHER'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_admin_credential_filters_and_statistics(self):
        self.issue()
        self.issue(issued_at=self.now-timedelta(days=3), expires_at=self.now-timedelta(days=1))
        foreign = self.issue(self.other_award)
        revoke_credential(public_reference=foreign.public_reference, actor=self.admin, reason='Revocation')
        self.as_admin()
        for status in ['VALID', 'EXPIRED', 'REVOKED']:
            self.assertEqual(self.client.get('/api/admin/credentials/', {'status': status}).json()['count'], 1)
        self.assertEqual(self.client.get('/api/admin/credentials/', {'student_id': str(self.student.pk)}).json()['count'], 2)
        self.assertEqual(self.client.get('/api/admin/credentials/', {'student_id': 'bad'}).status_code, 400)
        self.assertEqual(self.client.get('/api/admin/credentials/', {'status': 'BAD'}).status_code, 400)
        stats = self.client.get('/api/admin/statistics/').json()
        self.assertEqual(stats['students'], 2); self.assertEqual(stats['recognized_skills'], 1)
        self.assertEqual(stats['verified_achievements'], 2)
        self.assertEqual(stats['credentials']['total'], 3)
        self.assertEqual(stats['credentials']['revoked'], 1)

    def test_passport_admin_listing_detail_and_versions(self):
        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            self.issue()
        self.assertEqual(len(callbacks), 1)
        self.assertTrue(DigitalPassport.objects.filter(student=self.student).exists(), list(CredentialPassportRefresh.objects.values()))
        passport = DigitalPassport.objects.get(student=self.student)
        self.as_admin()
        self.assertEqual(self.client.get('/api/admin/passports/', {'student_id': str(self.student.pk)}).json()['count'], 1)
        self.assertEqual(self.client.get(f'/api/admin/passports/{passport.pk}/').json()['latest_version']['skills'][0]['subcategory'], 'Reasoning')
        self.assertEqual(self.client.get(f'/api/admin/passports/{passport.pk}/versions/').json()['count'], 1)
        self.assertEqual(self.client.patch(f'/api/admin/passports/{passport.pk}/', {}, format='json').status_code, 405)

    def test_query_counts_do_not_grow_with_credential_or_skill_page(self):
        self.issue()
        def count(route):
            with CaptureQueriesContext(connection) as captured:
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200, response.data)
            return len(captured)
        cred_count = count('/api/student/credentials/')
        skill_count = count('/api/student/skills/')
        for number in range(6):
            skill = Skill.objects.create(skill_code=f'EXTRA-{number}', skill_name='Extra', category='AI', subcategory='Reasoning', description='Extra', stamp_type='FOCUSED', badge_asset_id='extra')
            award = self.make_award(self.student, skill)
            self.issue(award)
        self.assertLessEqual(count('/api/student/credentials/'), cred_count)
        self.assertEqual(count('/api/student/skills/'), skill_count)
        self.assertLessEqual(cred_count, 6); self.assertLessEqual(skill_count, 5)

    def test_session_authentication_and_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.admin, backend='apps.accounts.authentication.AdminPasswordBackend')
        self.assertEqual(client.get('/api/admin/students/').status_code, 200)
        self.assertEqual(client.post('/api/admin/students/', {}, format='json').status_code, 403)
        client.force_login(self.user, backend='apps.accounts.authentication.StudentOTPBackend')
        self.assertEqual(client.get('/api/student/dashboard/').status_code, 200)
        self.assertEqual(client.get('/api/students/students/API-one/').status_code, 200)

    def test_subcategory_is_frozen_in_renderer_context_and_pdf(self):
        import pymupdf
        from passport_pdf_renderer import render_passport_pdf
        with self.captureOnCommitCallbacks(execute=True):
            self.issue()
        version_id = DigitalPassport.objects.get(student=self.student).latest_version_id
        Skill.objects.filter(pk=self.skill.pk).update(subcategory='Changed catalog')
        context = _render_context(_version_queryset().get(pk=version_id))
        self.assertEqual(context['skills'][0]['subcategory'], 'Reasoning')
        with pymupdf.open(stream=render_passport_pdf(context), filetype='pdf') as pdf:
            text = '\n'.join(page.get_text() for page in pdf)
        self.assertIn('REASONING', text.upper())
        self.assertNotIn('Changed catalog', text)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PassportVersionSkill.objects.filter(version_id=version_id).update(subcategory='Tampered')

    def test_unsupported_student_management_methods_return_405(self):
        self.as_admin()
        self.assertEqual(self.client.post(f'/api/admin/students/{self.student.pk}/', {}, format='json').status_code, 405)
        self.assertEqual(self.client.patch('/api/admin/students/', {}, format='json').status_code, 405)

    def test_admin_list_and_statistics_query_counts_are_bounded(self):
        self.as_admin()
        def count(route):
            with CaptureQueriesContext(connection) as captured:
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200, response.data)
            return len(captured)
        # Warm permission caches; adding rows must not add per-record lookups.
        count('/api/admin/statistics/')
        before_students = count('/api/admin/students/')
        before_statistics = count('/api/admin/statistics/')
        for number in range(8):
            self.make_student(f'extra-{number}')
        self.assertEqual(count('/api/admin/students/'), before_students)
        self.assertEqual(count('/api/admin/statistics/'), before_statistics)
        self.assertLessEqual(before_students, 2)
        self.assertLessEqual(before_statistics, 8)

    def test_input_shape_validation_and_nested_achievement_bound(self):
        self.as_admin()
        for route in ['students/', 'credentials/issue/']:
            for payload in [[], ['invalid'], 'invalid']:
                self.assertEqual(self.client.post('/api/admin/'+route, payload, format='json').status_code, 400)
        for _ in range(101):
            self.make_award(self.student)
        self.client.force_authenticate(self.user)
        data = self.client.get('/api/student/skills/').json()['results'][0]
        self.assertEqual(len(data['achievements']), 100)
        self.assertEqual(data['achievements_limit'], 100)
        self.assertEqual(self.client.get('/api/student/achievements/', {'skill_id': str(self.skill.pk)}).json()['count'], 102)
        self.assertEqual(self.client.get('/api/student/achievements/', {'skill_id': 'invalid'}).status_code, 400)

    def test_snapshot_database_guard_rejects_mismatched_subcategory(self):
        passport = DigitalPassport.objects.create(student=self.student)
        version = PassportVersion.objects.create(passport=passport, version_number=1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            PassportVersionSkill.objects.create(
                version=version, skill=self.skill, skill_code=self.skill.skill_code,
                skill_name=self.skill.skill_name, category=self.skill.category,
                subcategory='False classification', description=self.skill.description,
                stamp_type=self.skill.stamp_type, badge_asset_id=self.skill.badge_asset_id,
            )
