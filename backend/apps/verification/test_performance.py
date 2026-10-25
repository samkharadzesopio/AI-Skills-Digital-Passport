"""Reproducible local measurements, not a production load certification."""
import json
import statistics
import time
from datetime import timedelta

from django.db import connection, transaction
from django.test import TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from apps.credentials.models import Credential, CredentialAchievement, CredentialLifecycleEvent
from apps.passports.test_documents import DocumentDataMixin
from apps.skills.models import AchievementSourceEvent, Skill, VerifiedAchievement
from apps.students.models import Student
from apps.integrations.importers.durable import process_import
from .services import CredentialVerificationService
from .passport_service import PassportVerificationService


@override_settings(BTU_CLASSROOM_ISSUER_REFERENCE='BTU-UNIVERSITY',
                   VERIFICATION_TRUSTED_ISSUER_REFERENCES=['BTU-UNIVERSITY'],
                   BTU_AUTHORIZED_COMPLETION_SOURCES=['BTU_EXCEL'])
class PopulationPerformanceTests(DocumentDataMixin, TransactionTestCase):
    def test_5000_student_population_queries_and_import_replay(self):
        started = time.perf_counter()
        # Existing mixin supplies one student/credential/passport. Bulk fixture
        # setup obeys DB constraints; it does not claim service-path ingestion speed.
        students = [Student(external_student_id=f'PERF-{i}', first_name='Synthetic', last_name='Population',
                            email=f'perf-{i}@example.org', program='AI', education_level='Bachelor', student_status='Active') for i in range(4999)]
        issued = self.now - timedelta(days=1)
        with transaction.atomic():
            Student.objects.bulk_create(students, batch_size=500)
            sources = AchievementSourceEvent.objects.bulk_create([
                AchievementSourceEvent(source='PERFORMANCE_SYNTHETIC', source_event_id=str(i), payload_sha256='d'*64) for i in range(4999)
            ], batch_size=500)
            awards = VerifiedAchievement.objects.bulk_create([
                VerifiedAchievement(student=s, skill=self.skill, source_event=e, earned_on=issued.date(), verification_status='VERIFIED')
                for s, e in zip(students, sources)
            ], batch_size=500)
            credentials = Credential.objects.bulk_create([
                Credential(student=s, issuer=self.issuer, issuer_reference=self.issuer.reference, issuer_name=self.issuer.display_name,
                           idempotency_key=f'PERFORMANCE-{i}', request_sha256='b'*64, issued_at=issued)
                for i, s in enumerate(students)
            ], batch_size=500)
            CredentialAchievement.objects.bulk_create([
                CredentialAchievement(credential=c, achievement=a) for c, a in zip(credentials, awards)
            ], batch_size=500)
            CredentialLifecycleEvent.objects.bulk_create([
                CredentialLifecycleEvent(credential=c, event_type='ISSUED', occurred_at=issued, actor_reference=self.issuer.reference)
                for c in credentials
            ], batch_size=500)
        self.assertEqual(Student.objects.count(), 5000)
        self.assertEqual(Credential.objects.count(), 5000)
        fixture_seconds = time.perf_counter() - started
        with connection.cursor() as cursor:
            cursor.execute('ANALYZE credentials')
        plan = json.loads(Credential.objects.filter(public_reference=credentials[2499].public_reference).explain(format='json', analyze=True))
        self.assertIn('Index', json.dumps(plan))
        samples = []
        credential_service = CredentialVerificationService()
        for i in range(100):
            start = time.perf_counter()
            with self.assertNumQueries(1):
                result = credential_service.verify(credentials[(i * 47) % 4999].public_reference)
            self.assertEqual(result['status'], 'VALID')
            samples.append((time.perf_counter() - start) * 1000)
        passport_samples = []
        for _ in range(100):
            start = time.perf_counter()
            with self.assertNumQueries(2):
                result = PassportVerificationService().verify(self.version.passport.public_reference)
            self.assertEqual(result['status'], 'VALID')
            passport_samples.append((time.perf_counter() - start) * 1000)
        for code in ['AI_LITERACY', 'AI_FUNDAMENTALS']:
            Skill.objects.create(skill_code=code, skill_name=code, category='AI Skill', description='Synthetic import', stamp_type='FOCUSED', badge_asset_id='test')
        rows = [{'external_student_id': students[i].external_student_id, 'source_event_id': f'PERF-IMPORT-{i}',
                 'course_id': 'AI-101', 'completion_status': 'completed', 'grade': 90, 'passed': True,
                 'completion_date': issued.date().isoformat()} for i in range(20)]
        start = time.perf_counter()
        with CaptureQueriesContext(connection) as queries:
            imported = process_import(rows, source='BTU_EXCEL')
        import_seconds, import_queries = time.perf_counter() - start, len(queries)
        start = time.perf_counter()
        replay = process_import(rows, source='BTU_EXCEL')
        replay_seconds = time.perf_counter() - start
        self.assertEqual((imported['issued'], replay['skipped']), (20, 20))
        self.assertEqual(Credential.objects.count(), 5020)
        print('LOCAL_PERFORMANCE ' + json.dumps({
            'students': 5000, 'initial_credentials': 5000,
            'fixture_setup_seconds': round(fixture_seconds, 3), 'credential_samples': 100,
            'credential_queries': 1, 'credential_median_ms': round(statistics.median(samples), 3),
            'credential_p95_ms': round(sorted(samples)[94], 3),
            'passport_samples': 100, 'passport_queries': 2,
            'passport_median_ms': round(statistics.median(passport_samples), 3),
            'passport_p95_ms': round(sorted(passport_samples)[94], 3),
            'import_events': 20, 'import_seconds': round(import_seconds, 3), 'import_queries': import_queries,
            'replay_seconds': round(replay_seconds, 3), 'duplicate_credentials': 0,
            'indexed_public_reference_lookup': True,
        }, sort_keys=True))
