import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import connection, close_old_connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from apps.accounts.models import User, AuthRateLimitBucket
from apps.skills.models import Skill, AchievementSourceEvent, VerifiedAchievement
from apps.students.models import Student
from rest_framework.test import APIClient
from .service import RecommendationService


@override_settings(VERIFICATION_TRUSTED_ISSUER_REFERENCES=['BTU-UNIVERSITY'])
class PopulationAndConcurrencyTests(TransactionTestCase):
    def student(self, external, email):
        return Student.objects.create(external_student_id=external,first_name='Synthetic',last_name='Student',email=email,program='Computing',education_level='Bachelor',student_status='Active')

    def test_5000_student_fixture_uses_scoped_constant_queries(self):
        beginner=self.student('DEMO-STUDENT-BEGINNER','beginner.guidance@btu.edu.ge')
        advanced=self.student('DEMO-STUDENT-ADVANCED','advanced.guidance@btu.edu.ge')
        others=Student.objects.bulk_create([Student(external_student_id=f'GUIDANCE-POP-{i}',first_name='Synthetic',last_name='Student',email=f'guidance-pop-{i}@btu.edu.ge',program='Computing',education_level='Bachelor',student_status='Active') for i in range(4998)],batch_size=500)
        skill=Skill.objects.create(skill_code='AI_LITERACY',skill_name='AI Literacy',category='AI Skill',description='Synthetic',stamp_type='FOCUSED',badge_asset_id='test')
        sources=AchievementSourceEvent.objects.bulk_create([AchievementSourceEvent(source='PERFORMANCE_SYNTHETIC',source_event_id=f'GUIDANCE-{i}',payload_sha256='b'*64) for i in range(4998)],batch_size=500)
        VerifiedAchievement.objects.bulk_create([VerifiedAchievement(student=s,skill=skill,source_event=e,earned_on='2026-01-01',verification_status='VERIFIED') for s,e in zip(others,sources)],batch_size=500)
        self.assertEqual(Student.objects.count(),5000)
        samples=[]
        results=[]
        for i in range(30):
            start=time.perf_counter()
            with self.assertNumQueries(3):
                result=RecommendationService().recommend(beginner.pk if i%2==0 else advanced.pk)
            samples.append((time.perf_counter()-start)*1000)
            if i<2:
                results.append([c['course_id'] for c in result['recommendations']])
        self.assertNotEqual(results[0],results[1])
        self.assertEqual(VerifiedAchievement.objects.count(),4998)
        print('RECOMMENDATION_PERFORMANCE '+json.dumps({'students':5000,'achievement_rows':4998,'requests':30,'queries_per_service_call':3,
              'median_ms':round(statistics.median(samples),3),'p95_ms':round(sorted(samples)[28],3),
              'beginner_top':results[0],'advanced_top':results[1], 'analysis_mode':'RULE_BASED'},sort_keys=True))

    def test_shared_worker_rate_limit_is_atomic(self):
        student=self.student('DEMO-STUDENT-BEGINNER','concurrent.guidance@btu.edu.ge')
        user=User.objects.create_user(email=student.email,student=student,is_email_verified=True)
        from apps.accounts.otp_utils import security_digest
        key=security_digest('recommendations.rate.v1',str(user.pk))
        AuthRateLimitBucket.objects.create(bucket_digest=key,request_count=29,window_started_at=timezone.now())
        barrier=Barrier(2)
        def request(_):
            close_old_connections()
            try:
                client=APIClient()
                client.force_authenticate(user)
                barrier.wait(timeout=10)
                return client.get('/api/integrations/course-recommendations/').status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(request,range(2))),[200,429])
        self.assertEqual(AuthRateLimitBucket.objects.get(pk=key).request_count,30)
