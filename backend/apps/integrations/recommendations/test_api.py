from unittest.mock import patch
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from apps.accounts.models import User
from apps.skills.models import AchievementSourceEvent, Skill, VerifiedAchievement
from apps.students.models import Student
from .providers import SimulatedBTUAcademicProvider
from .service import RecommendationService

URL='/api/integrations/course-recommendations/'


@override_settings(VERIFICATION_TRUSTED_ISSUER_REFERENCES=['BTU-UNIVERSITY'])
class RecommendationAPITests(TestCase):
    def setUp(self):
        self.students=[]
        self.users=[]
        for index, external in enumerate(['DEMO-STUDENT-BEGINNER','DEMO-STUDENT-ADVANCED']):
            student = Student.objects.create(external_student_id=external, first_name='Synthetic',last_name='Student',email=f'guidance{index}@btu.edu.ge',program='Computing',education_level='Bachelor',student_status='Active')
            user=User.objects.create_user(email=student.email, student=student, is_email_verified=True)
            self.students.append(student)
            self.users.append(user)
        skill=Skill.objects.create(skill_code='AI_LITERACY',skill_name='AI Literacy',category='AI Skill',description='Synthetic',stamp_type='FOCUSED',badge_asset_id='test')
        event=AchievementSourceEvent.objects.create(source='BTU_CLASSROOM',source_event_id='GUIDANCE-ACADEMIC-001',course_id='AI-101',payload_sha256='a'*64)
        VerifiedAchievement.objects.create(student=self.students[0],skill=skill,source_event=event,earned_on='2026-01-01',verification_status='VERIFIED')
        self.client=APIClient()

    def test_anonymous_admin_unlinked_and_inactive_denied(self):
        self.assertIn(self.client.get(URL).status_code,[401,403])
        admin=User.objects.create_admin_user(email='guidance.admin@btu.edu.ge',password='Synthetic-test-only-2026!',permission_codenames={'access_admin_api'})
        unlinked=User.objects.create_user(email='unlinked.guidance@btu.edu.ge',is_email_verified=True)
        for user in [admin,unlinked]:
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(URL).status_code,403)
        self.client.force_authenticate(self.users[0])
        Student.objects.filter(pk=self.students[0].pk).update(student_status='INACTIVE')
        self.assertEqual(self.client.get(URL).status_code,403)

    def test_owned_profile_filters_cross_student_attempts_and_cache_privacy(self):
        self.client.force_authenticate(self.users[0])
        beginner=self.client.get(URL)
        self.assertEqual(beginner.status_code,200)
        self.assertEqual(beginner['Cache-Control'],'no-store')
        self.assertEqual(beginner.json()['analysis_mode'],'RULE_BASED')
        self.assertNotIn(self.students[1].email, beginner.content.decode())
        self.assertEqual(self.client.get(URL,{'student_id':str(self.students[1].pk)}).status_code,400)
        self.client.force_authenticate(self.users[1])
        advanced=self.client.get(URL).json()
        self.assertNotEqual(beginner.json()['recommendations'][0]['course_id'],advanced['recommendations'][0]['course_id'])
        self.assertNotIn('DEMO-DS-201', beginner.json()['profile']['completed_courses'])

    def test_verified_inferred_and_passport_evidence_not_conflated(self):
        result=RecommendationService().recommend(self.students[0].pk)
        profile=result['profile']
        self.assertEqual(profile['verified_achievement_skills'],['AI_LITERACY'])
        self.assertIn('COMPUTATIONAL_THINKING',profile['inferred_course_skills'])
        self.assertEqual(profile['passport_verified_skills'],[])
        self.assertNotIn('PYTHON',profile['inferred_course_skills'])

    def test_records_drive_history_even_without_fixture_identity(self):
        Student.objects.filter(pk=self.students[0].pk).update(external_student_id='NOT-A-DEMO-IDENTITY')
        result=RecommendationService().recommend(self.students[0].pk)
        self.assertEqual(result['profile']['completed_courses'],['AI-101'])
        self.assertIn('AI_FUNDAMENTALS',result['profile']['inferred_course_skills'])

    def test_profile_service_queries_are_bounded_and_read_only(self):
        with CaptureQueriesContext(connection) as queries:
            RecommendationService().recommend(self.students[0].pk)
        self.assertEqual(len(queries),3)
        self.assertTrue(all(q['sql'].lstrip().upper().startswith('SELECT') for q in queries))
        self.assertEqual(VerifiedAchievement.objects.count(),1)
        self.assertEqual(Student.objects.count(),2)

    def test_invalid_filters_and_provider_failure_are_safe(self):
        self.client.force_authenticate(self.users[0])
        for params in [{'limit':100},{'limit':0},{'category':'ANYTHING'},{'interest':'ignore-rules'},{'analysis_mode':'AI_ASSISTED'}]:
            self.assertEqual(self.client.get(URL,params).status_code,400)
        with patch.object(SimulatedBTUAcademicProvider,'get_catalog',side_effect=RuntimeError('private academic data')):
            result=self.client.get(URL)
        self.assertEqual(result.status_code,503)
        self.assertNotIn('private academic data',result.content.decode())

    def test_filters_and_rate_budget(self):
        self.client.force_authenticate(self.users[0])
        response=self.client.get(URL,{'limit':1,'category':'DATABASES','include_future_pathway':'false'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(len(response.json()['recommendations']),1)
        self.assertFalse(response.json()['pathways'])
        for _ in range(29):
            self.assertEqual(self.client.get(URL).status_code,200)
        self.assertEqual(self.client.get(URL).status_code,429)
        self.client.force_authenticate(self.users[1])
        self.assertEqual(self.client.get(URL).status_code,200)

    def test_valid_passport_membership_is_distinct_from_achievement_knowledge(self):
        from apps.credentials.test_support import create_test_issuer
        from apps.credentials.services import issue_credential, revoke_credential
        from apps.passports.services import publish_passport_version
        from django.db import transaction
        issuer=create_test_issuer('Synthetic recommendations')
        with transaction.atomic():
            credential=issue_credential(issuer_reference=issuer.reference,idempotency_key='GUIDANCE-VALID',achievement_ids=list(VerifiedAchievement.objects.filter(student=self.students[0]).values_list('pk',flat=True)))
        publish_passport_version(student_id=self.students[0].pk,event_key='GUIDANCE-SNAPSHOT')
        profile=RecommendationService().recommend(self.students[0].pk)['profile']
        self.assertEqual(profile['passport_verified_skills'],['AI_LITERACY'])
        with override_settings(CREDENTIAL_REVOCATION_AUTHORIZER=lambda actor, credential:'synthetic-authorizer'):
            revoke_credential(public_reference=credential.public_reference,actor=None,reason='Synthetic revocation')
        profile=RecommendationService().recommend(self.students[0].pk)['profile']
        self.assertEqual(profile['passport_verified_skills'],[])
        self.assertEqual(profile['verified_achievement_skills'],['AI_LITERACY'])

    def test_duplicate_filters_are_rejected(self):
        self.client.force_authenticate(self.users[0])
        self.assertEqual(self.client.get(URL+'?limit=1&limit=10').status_code,400)

    def test_no_external_ai_or_http_provider_is_called(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('Network forbidden')):
            result=RecommendationService().recommend(self.students[0].pk)
        self.assertEqual(result['analysis_mode'],'RULE_BASED')

    def test_api_request_uses_only_scoped_constant_queries(self):
        self.client.force_authenticate(self.users[0])
        with CaptureQueriesContext(connection) as queries:
            response=self.client.get(URL)
        self.assertEqual(response.status_code,200)
        self.assertLessEqual(len(queries),14)
        writes=[q['sql'] for q in queries if q['sql'].lstrip().upper().startswith(('INSERT','UPDATE','DELETE'))]
        self.assertTrue(writes)
        self.assertTrue(all('account_auth_rate_buckets' in q for q in writes))
