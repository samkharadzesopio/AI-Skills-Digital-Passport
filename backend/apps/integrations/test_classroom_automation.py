from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.db import close_old_connections, connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.credentials.models import Credential, CredentialIssuer, CredentialLifecycleEvent
from apps.credentials.test_support import create_test_issuer
from apps.skills.models import AchievementSourceEvent, Skill, VerifiedAchievement
from apps.students.models import Student
from .classroom_automation import ClassroomCredentialAutomation, process_event, receive
from .models import ClassroomSyncEvent as Event

RECORD = {
    'event_id': 'TRUSTED-EVENT-001', 'student_id': 'BTU-SYNTHETIC-001',
    'course_id': 'AI-101', 'course_name': 'Synthetic course',
    'completion_status': 'completed', 'passed': True, 'grade': 90,
    'completion_date': '2026-01-01',
}


@override_settings(BTU_CLASSROOM_ISSUER_REFERENCE='BTU-UNIVERSITY')
class ClassroomAutomationTests(TransactionTestCase):
    def setUp(self):
        self.student = Student.objects.create(
            external_student_id=RECORD['student_id'], first_name='Synthetic', last_name='Student',
            email='synthetic@btu.edu.ge', program='Synthetic', education_level='Bachelor', student_status='Active',
        )
        self.issuer = create_test_issuer('Synthetic BTU')
        for code in ['AI_LITERACY', 'AI_FUNDAMENTALS']:
            Skill.objects.create(skill_code=code, skill_name=code, category='AI Skill',
                                 description='Synthetic', stamp_type='FOCUSED', badge_asset_id='test')
        self.classroom = Mock()
        self.classroom.get_completions.return_value = [deepcopy(RECORD)]
        self.service = ClassroomCredentialAutomation(self.classroom)

    def sync(self, **changes):
        self.classroom.get_completions.return_value = [{**RECORD, **changes}]
        return self.service.synchronize(dry_run=False)

    def test_valid_completion_multiple_skills_and_lifecycle(self):
        result = self.sync()
        self.assertEqual((result['processed'], result['issued'], result['failed']), (1, 1, 0))
        event = Event.objects.get()
        self.assertEqual(event.state, Event.State.CREDENTIAL_ISSUED)
        self.assertEqual(event.achievement_event.achievements.count(), 2)
        self.assertEqual(event.credential.achievements.count(), 2)
        self.assertEqual(CredentialLifecycleEvent.objects.get().event_type, 'ISSUED')
        from apps.passports.models import DigitalPassport
        # The credential lifecycle callback publishes exactly one unified Passport.
        self.assertEqual(DigitalPassport.objects.count(), 1)
        self.assertEqual(DigitalPassport.objects.get().versions.count(), 1)

    def test_unknown_student_is_durably_failed(self):
        self.assertEqual(self.sync(student_id='UNKNOWN')['failed'], 1)
        self.assertEqual(Event.objects.get().error_code, 'UNKNOWN_STUDENT')
        self.assertFalse(Credential.objects.exists())
        self.assertEqual(Student.objects.count(), 1)

    def test_unknown_course(self):
        self.assertEqual(self.sync(course_id='NOT-APPROVED')['failed'], 1)
        self.assertFalse(VerifiedAchievement.objects.exists())

    def test_failed_and_incomplete_courses(self):
        for changes in [{'passed': False}, {'completion_status': 'in_progress'}, {'grade': 10}]:
            Event.objects.all().delete()
            self.assertEqual(self.sync(**changes)['failed'], 1)
        self.assertFalse(Credential.objects.exists())

    def test_invalid_grade_and_future_date(self):
        for changes in [{'grade': True}, {'grade': 101}, {'completion_date': '2999-01-01'}]:
            Event.objects.all().delete()
            self.assertEqual(self.sync(**changes)['failed'], 1)
        self.assertFalse(Credential.objects.exists())

    def test_unknown_skill_and_missing_mapping(self):
        with patch('apps.integrations.classroom_automation.ApprovedAICourseRepository.get_approved_courses', return_value=[
            {'course_id': 'AI-101', 'minimum_grade': 51, 'skill_codes': ['UNKNOWN']},
        ]):
            self.assertEqual(self.sync()['failed'], 1)
        self.assertEqual(Event.objects.get().error_code, 'UNKNOWN_SKILL')
        Event.objects.all().delete()
        with patch('apps.integrations.classroom_automation.ApprovedAICourseRepository.get_approved_courses', return_value=[
            {'course_id': 'AI-101', 'minimum_grade': 51},
        ]):
            self.assertEqual(self.sync()['failed'], 1)
        self.assertFalse(Credential.objects.exists())

    def test_disabled_or_ambiguous_mapping(self):
        for courses in [[{'course_id': 'AI-101', 'minimum_grade': 51, 'enabled': False}],
                        [{'course_id': 'AI-101'}, {'course_id': 'AI-101'}]]:
            Event.objects.all().delete()
            with patch('apps.integrations.classroom_automation.ApprovedAICourseRepository.get_approved_courses', return_value=courses):
                self.assertEqual(self.sync()['failed'], 1)
        self.assertFalse(Credential.objects.exists())

    def test_duplicate_event_survives_new_service_instance(self):
        self.sync()
        result = ClassroomCredentialAutomation(self.classroom).synchronize(dry_run=False)
        self.assertEqual((result['issued'], result['skipped']), (0, 1))
        self.assertEqual(VerifiedAchievement.objects.count(), 2)
        self.assertEqual(Credential.objects.count(), 1)
        self.assertEqual(Event.objects.get().attempts, 1)

    def test_conflicting_payload_preserves_original(self):
        self.sync()
        self.assertEqual(self.sync(grade=91)['failed'], 1)
        self.assertEqual(Event.objects.get().payload['grade'], 90)
        self.assertEqual(Credential.objects.count(), 1)

    def test_issuance_failure_preserves_achievements_and_replay_recovers(self):
        with patch('apps.integrations.classroom_automation.issue_credential', side_effect=RuntimeError('private DB text')):
            self.assertEqual(self.sync()['failed'], 1)
        event = Event.objects.get()
        original_ids = set(VerifiedAchievement.objects.values_list('pk', flat=True))
        self.assertEqual(len(original_ids), 2)
        self.assertIsNotNone(event.achievement_event_id)
        self.assertEqual(event.state, 'FAILED')
        self.assertTrue(event.retryable)
        self.assertNotIn('private', event.error_code)
        self.assertFalse(Credential.objects.exists())
        # Before the retry deadline, another sync does not consume another attempt.
        self.sync()
        self.assertEqual(Event.objects.get().attempts, 1)
        Event.objects.update(next_retry_at=timezone.now())
        self.assertEqual(self.sync()['issued'], 1)
        self.assertEqual(set(VerifiedAchievement.objects.values_list('pk', flat=True)), original_ids)
        self.assertEqual(Credential.objects.count(), 1)

    def test_missing_issuer_fails_closed_then_recovers(self):
        with patch('apps.integrations.classroom_automation.CredentialIssuer.objects.filter') as issuer_filter:
            issuer_filter.return_value.exists.return_value = False
            self.assertEqual(self.sync()['failed'], 1)
            self.assertFalse(VerifiedAchievement.objects.exists())
        self.assertEqual(process_event(Event.objects.get().pk, force=True), 'issued')

    @override_settings(BTU_CLASSROOM_ISSUER_REFERENCE=None)
    def test_unconfigured_issuer(self):
        self.assertEqual(self.sync()['failed'], 1)
        self.assertFalse(Credential.objects.exists())

    @override_settings(BTU_CLASSROOM_ISSUER_REFERENCE='UNAPPROVED-ISSUER')
    def test_non_btu_issuer_configuration_cannot_issue(self):
        self.assertEqual(self.sync()['failed'], 1)
        event = Event.objects.get()
        self.assertEqual(event.error_code, 'ImproperlyConfigured')
        self.assertFalse(VerifiedAchievement.objects.exists())
        self.assertFalse(Credential.objects.exists())

    def test_mapping_change_does_not_rewrite_partial_achievements(self):
        with patch('apps.integrations.classroom_automation.issue_credential', side_effect=RuntimeError()):
            self.sync()
        with patch('apps.integrations.classroom_automation.ApprovedAICourseRepository.get_approved_courses', return_value=[
            {'course_id': 'AI-101', 'minimum_grade': 51, 'skill_codes': ['AI_LITERACY']},
        ]):
            self.assertEqual(process_event(Event.objects.get().pk, force=True), 'failed')
        self.assertFalse(Event.objects.get().retryable)
        self.assertEqual(VerifiedAchievement.objects.count(), 2)
        self.assertFalse(Credential.objects.exists())

    def test_mapping_change_after_issuance_does_not_issue_again(self):
        self.sync()
        with patch('apps.integrations.classroom_automation.ApprovedAICourseRepository.get_approved_courses', return_value=[]):
            self.assertEqual(self.sync()['skipped'], 1)
        self.assertEqual(Credential.objects.count(), 1)

    def test_retry_budget_is_bounded(self):
        with patch('apps.integrations.classroom_automation.issue_credential', side_effect=RuntimeError()):
            self.sync()
            for _ in range(8):
                process_event(Event.objects.get().pk, force=True)
        event = Event.objects.get()
        self.assertEqual(event.attempts, 5)
        self.assertFalse(event.retryable)
        self.assertIsNone(event.next_retry_at)

    def test_dry_run_writes_nothing(self):
        result = self.service.synchronize(dry_run=True)
        self.assertEqual(result['would_issue'], 1)
        for model in [Event, AchievementSourceEvent, VerifiedAchievement, Credential, CredentialLifecycleEvent]:
            self.assertEqual(model.objects.count(), 0)

    def test_command_resumes_crash_between_stages(self):
        from .classroom_automation import _record_achievements
        pk = receive(RECORD)
        self.assertTrue(_record_achievements(pk, False))
        self.assertEqual(Event.objects.get().state, 'ACHIEVEMENTS_RECORDED')
        call_command('retry_classroom_events', verbosity=0)
        self.assertEqual(Event.objects.get().state, 'CREDENTIAL_ISSUED')
        self.assertEqual(Credential.objects.count(), 1)

    def test_parallel_duplicate_events(self):
        barrier = Barrier(2)
        def run(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return ClassroomCredentialAutomation(self.classroom).synchronize(dry_run=False)
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(run, range(2)))
        self.assertEqual(sum(r['issued'] for r in results), 1)
        self.assertEqual(sum(r['skipped'] for r in results), 1)
        self.assertEqual(Credential.objects.count(), 1)
        self.assertEqual(VerifiedAchievement.objects.count(), 2)

    def test_api_permission_dry_run_and_server_source_boundary(self):
        client = APIClient()
        url = '/api/integrations/classroom/sync/'
        self.assertIn(client.post(url, {}, format='json').status_code, [401, 403])
        admin = User.objects.create_admin_user(email='synthetic.admin@btu.edu.ge', password='Synthetic-test-only-2026!', permission_codenames={'import_completions'})
        client.force_authenticate(admin)
        self.assertEqual(client.post(url, {}, format='json').status_code, 403)
        authorized = User.objects.create_admin_user(email='sync.admin@btu.edu.ge', password='Synthetic-test-only-2026!', permission_codenames={'sync_classroom'})
        client.force_authenticate(authorized)
        with patch('apps.integrations.classroom_automation.ClassroomService.get_completions', return_value=[RECORD]):
            self.assertEqual(client.post(url, {}, format='json').status_code, 200)
            self.assertFalse(Event.objects.exists())
            self.assertEqual(client.post(url, {'events': [RECORD], 'source': 'FORGED', 'dry_run': False}, format='json').status_code, 400)
            response = client.post(url, {'dry_run': False}, format='json')
            self.assertEqual(response.json()['issued'], 1)
        event = Event.objects.get()
        self.assertEqual(event.requested_by, authorized)
        self.assertEqual(client.get('/api/integrations/classroom/events/').status_code, 200)
        self.assertEqual(client.post(f'/api/integrations/classroom/events/{event.pk}/retry/', {}, format='json').json()['result'], 'skipped')

    def test_admin_sync_requires_csrf_with_session(self):
        admin = User.objects.create_admin_user(email='csrf.admin@btu.edu.ge', password='Synthetic-test-only-2026!', permission_codenames={'sync_classroom'})
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(admin, backend='apps.accounts.authentication.AdminPasswordBackend')
        self.assertEqual(client.post('/api/integrations/classroom/sync/', {'dry_run': False}, format='json').status_code, 403)

    def test_untrusted_provenance_rejected(self):
        self.assertEqual(self.sync(source='ARBITRARY_UPLOAD')['failed'], 1)
        self.assertFalse(Event.objects.exists())
        self.assertFalse(Credential.objects.exists())

    def test_existing_achievement_without_inbox_is_recovered(self):
        from .achievement_adapter import award_classroom_skills
        existing = award_classroom_skills(RECORD, ['AI_LITERACY', 'AI_FUNDAMENTALS'])
        self.assertEqual(self.sync()['issued'], 1)
        self.assertEqual(set(Event.objects.get().credential.achievements.values_list('pk', flat=True)),
                         set(VerifiedAchievement.objects.values_list('pk', flat=True)))
        self.assertEqual(VerifiedAchievement.objects.count(), 2)

    def test_failed_issuance_transaction_rolls_back_credential_but_not_achievements(self):
        from apps.credentials.services import issue_credential
        def fail_after_issuing(**kwargs):
            issue_credential(**kwargs)
            raise RuntimeError('simulate transaction failure')
        with patch('apps.integrations.classroom_automation.issue_credential', side_effect=fail_after_issuing):
            self.assertEqual(self.sync()['failed'], 1)
        self.assertFalse(Credential.objects.exists())
        self.assertFalse(CredentialLifecycleEvent.objects.exists())
        self.assertEqual(VerifiedAchievement.objects.count(), 2)
        self.assertEqual(process_event(Event.objects.get().pk, force=True), 'issued')

    def test_dry_run_of_issued_event_skips_without_changing_attempts(self):
        self.sync()
        result = self.service.synchronize(dry_run=True)
        self.assertEqual((result['would_issue'], result['skipped']), (0, 1))
        self.assertEqual(Event.objects.get().attempts, 1)

    def test_caller_owned_transaction_rejected_before_live_writes(self):
        from django.core.exceptions import ImproperlyConfigured
        from django.db import transaction
        with transaction.atomic(), self.assertRaises(ImproperlyConfigured):
            self.sync()
        self.assertFalse(Event.objects.exists())

    def test_transient_database_abort_is_durable_and_bounded(self):
        from django.db import OperationalError
        with patch('apps.integrations.classroom_automation._record_achievements', side_effect=OperationalError('private db message')):
            pk = receive(RECORD)
            for _ in range(5):
                self.assertEqual(process_event(pk, force=True), 'failed')
        event = Event.objects.get()
        self.assertEqual(event.attempts, 5)
        self.assertFalse(event.retryable)
        self.assertEqual(event.error_code, 'OperationalError')

    def test_preview_deduplicates_and_commands_use_same_pipeline(self):
        from io import StringIO
        self.classroom.get_completions.return_value = [RECORD, RECORD]
        result = self.service.synchronize(dry_run=True)
        self.assertEqual((result['would_issue'], result['skipped']), (1, 1))
        output = StringIO()
        with patch('apps.integrations.classroom_automation.ClassroomService.get_completions', return_value=[RECORD]):
            call_command('sync_classroom', stdout=output)
            self.assertFalse(Event.objects.exists())
            call_command('sync_classroom', apply=True, stdout=output)
            self.assertEqual(Credential.objects.count(), 1)
