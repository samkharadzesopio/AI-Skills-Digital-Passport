"""Synthetic-provider automation regressions on actual disposable PostgreSQL."""
import copy
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.db import close_old_connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import SecurityAudit, User
from apps.credentials.models import Credential
from apps.credentials.test_support import create_test_issuer
from apps.passports.models import DigitalPassport, PassportVersion
from apps.skills.models import Skill, VerifiedAchievement
from apps.students.models import Student
from .importers.mapping import digest
from .importers.profiles import provision_profile
from .importers.sheet_source import SheetUnavailable
from .models import ImportRun, SpreadsheetAward, SpreadsheetPreview
from .test_spreadsheet_mapping import HEADERS, ROW, definition, grid

TARGET = {'spreadsheet_id': 'SYNTHETIC_SHEET_ID', 'worksheet': 'Passport Skill Records'}
BASE = '/api/integrations/import/automatic-sources/'


@override_settings(BTU_CLASSROOM_ISSUER_REFERENCE='BTU-UNIVERSITY',
                   BTU_AUTHORIZED_COMPLETION_SOURCES=['BTU_GOOGLE_SHEETS'],
                   BTU_SPREADSHEET_GOOGLE_SOURCES={'approved': TARGET})
class AutomationTests(TransactionTestCase):
    def setUp(self):
        self.admin = User.objects.create_admin_user(email='automatic-admin@btu.edu.ge',
            password=secrets.token_urlsafe(32), permission_codenames=['import_completions'])
        self.other = User.objects.create_admin_user(email='automatic-other@btu.edu.ge',
            password=secrets.token_urlsafe(32), permission_codenames=['import_completions'])
        self.student = Student.objects.create(external_student_id=ROW[0], first_name='Synthetic',
            last_name='Student', email='automatic-student@btu.edu.ge', program='AI',
            education_level='Bachelor', student_status='ACTIVE')
        self.skill = Skill.objects.create(skill_code=ROW[2], skill_name='Synthetic skill',
            category='AI Skill', description='Synthetic catalog', stamp_type='FOCUSED', badge_asset_id='synthetic')
        create_test_issuer('Synthetic BTU')
        d = definition()
        d['google_source'] = 'approved'
        self.profile = provision_profile({'key': 'synthetic-auto', 'version': 1, 'source': 'BTU_GOOGLE_SHEETS',
            'kind': 'SKILL_AWARD', 'approval_reference': 'SYNTHETIC-INSTITUTIONAL-POLICY', 'definition': d})
        self.profile.enabled = True
        self.profile.save(update_fields=['enabled'])
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.rows = grid(ROW)

    def enable(self, actor=None):
        from .spreadsheet_automation import configure_automation
        return configure_automation(self.profile.pk, actor=actor or self.admin, enabled=True,
            interval_seconds=60, authorization_reference='SYNTHETIC-CONTINUING-AUTHORITY')

    def due(self):
        from .models import SpreadsheetAutomation
        SpreadsheetAutomation.objects.update(next_poll_at=timezone.now()-timedelta(seconds=1))

    def poll(self, side_effect=None):
        from .spreadsheet_automation import poll_due_sources
        def read(profile):
            return self.rows, digest({'target': TARGET, 'rows': self.rows})
        with patch('apps.integrations.spreadsheet_automation.read_profile_sheet', side_effect=side_effect or read), \
             patch('apps.integrations.importers.preview.read_profile_sheet', side_effect=side_effect or read):
            return poll_due_sources(limit=10)

    def test_default_off_api_no_automatic_issuance(self):
        response = self.client.get(BASE)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['results'][0]['enabled'])
        self.poll()
        self.assertFalse(Credential.objects.exists())
        self.assertFalse(SpreadsheetPreview.objects.exists())

    def test_explicit_current_admin_enable_and_disable_api(self):
        path = f'{BASE}{self.profile.pk}/'
        self.assertEqual(self.client.post(path, {'enabled': True}, format='json').status_code, 400)
        response = self.client.post(path, {'enabled': True, 'confirm': True, 'interval_seconds': 60,
            'authorization_reference': 'SYNTHETIC-CONTINUING-AUTHORITY'}, format='json')
        self.assertEqual(response.status_code, 200)
        from .models import SpreadsheetAutomation
        binding = SpreadsheetAutomation.objects.get()
        self.assertEqual(binding.actor_id, self.admin.pk)
        self.assertTrue(binding.enabled)
        self.assertEqual(self.client.post(path, {'enabled': False}, format='json').status_code, 200)
        binding.refresh_from_db()
        self.assertFalse(binding.enabled)

    def test_enable_rejects_caller_actor_source_and_missing_authority(self):
        body = {'enabled': True, 'confirm': True, 'interval_seconds': 60,
                'authorization_reference': 'SYNTHETIC-CONTINUING-AUTHORITY'}
        for field, value in [('actor_id', str(self.other.pk)), ('source_url', 'https://example.invalid'),
                             ('issuer', 'OTHER'), ('records', [])]:
            self.assertEqual(self.client.post(f'{BASE}{self.profile.pk}/', {**body, field: value}, format='json').status_code, 400)
        for value in ['', ' ', 'x'*256]:
            self.assertEqual(self.client.post(f'{BASE}{self.profile.pk}/', {**body, 'authorization_reference': value}, format='json').status_code, 400)
        for value in [0, 59, 86401, True, '60']:
            self.assertEqual(self.client.post(f'{BASE}{self.profile.pk}/', {**body, 'interval_seconds': value}, format='json').status_code, 400)

    def test_permission_and_source_profile_prerequisites(self):
        from .spreadsheet_automation import configure_automation
        from django.core.exceptions import PermissionDenied
        permission = Permission.objects.get(content_type__app_label='accounts', codename='import_completions')
        self.admin.user_permissions.remove(permission)
        with self.assertRaises(PermissionDenied):
            self.enable()
        self.admin.user_permissions.add(permission)
        with override_settings(BTU_AUTHORIZED_COMPLETION_SOURCES=[]):
            with self.assertRaises(Exception):
                self.enable()
        self.profile.enabled = False
        self.profile.save(update_fields=['enabled'])
        with self.assertRaises(Exception):
            self.enable()

    def test_automatic_confirmed_award_replay_and_new_record_preserve_passport(self):
        self.enable()
        self.poll()
        self.assertEqual((Credential.objects.count(), SpreadsheetAward.objects.count()), (1, 1))
        passport = DigitalPassport.objects.get()
        identity, first_issued = passport.pk, passport.first_issued_at
        initial_versions = PassportVersion.objects.count()
        initial_runs = ImportRun.objects.count()
        self.due(); self.poll()
        self.assertEqual((Credential.objects.count(), PassportVersion.objects.count(), ImportRun.objects.count()), (1, initial_versions, initial_runs))
        self.rows.append([ROW[0], 'SYNTHETIC-NEW-RECORD', ROW[2], '2026-01-02', 'CONFIRMED'])
        self.due(); self.poll()
        passport.refresh_from_db()
        self.assertEqual((Credential.objects.count(), SpreadsheetAward.objects.count()), (2, 2))
        self.assertEqual((passport.pk, passport.first_issued_at), (identity, first_issued))
        self.assertGreater(PassportVersion.objects.count(), initial_versions)

    def test_pending_rejected_unknown_conflicting_and_formulas_never_issue(self):
        self.enable()
        self.rows = grid([*ROW[:4], 'PENDING'], [ROW[0], 'R2', *ROW[2:4], 'REJECTED'],
            ['UNKNOWN', 'R3', *ROW[2:]], [ROW[0], 'R4', 'UNKNOWN', *ROW[3:]],
            [ROW[0], 'R5', *ROW[2:]], [ROW[0], 'R5', ROW[2], '2026-01-02', 'CONFIRMED'],
            [ROW[0], 'R6', ROW[2], '=NOW()', 'CONFIRMED'])
        self.poll()
        self.assertFalse(Credential.objects.exists())
        self.assertFalse(VerifiedAchievement.objects.exists())
        self.assertFalse(DigitalPassport.objects.exists())
        self.assertEqual(SpreadsheetPreview.objects.get().report['review_records'], 2)

    def test_pending_to_confirmed_discovered_without_manual_confirmation(self):
        self.enable()
        self.rows = grid([*ROW[:4], 'PENDING'])
        self.poll()
        self.assertFalse(Credential.objects.exists())
        self.rows = grid(ROW)
        self.due(); self.poll()
        self.assertEqual(Credential.objects.count(), 1)

    def test_duplicate_conflicting_prior_facts_and_invalid_student_isolation(self):
        self.enable(); self.poll()
        self.rows = grid(ROW, ROW, [ROW[0], ROW[1], ROW[2], '2026-01-02', 'CONFIRMED'])
        self.due(); self.poll()
        self.assertEqual(Credential.objects.count(), 1)
        self.assertEqual(SpreadsheetAward.objects.count(), 1)
        self.assertEqual(SpreadsheetPreview.objects.order_by('-created_at').first().report['invalid_records'], 3)

    def test_revoked_permission_disabled_actor_profile_or_source_prevents_poll_issuance(self):
        from .models import SpreadsheetPoll
        from .spreadsheet_automation import configure_automation
        permission = Permission.objects.get(content_type__app_label='accounts', codename='import_completions')
        self.enable()
        self.admin.user_permissions.remove(permission)
        self.poll()
        self.assertFalse(Credential.objects.exists())
        self.assertEqual(SpreadsheetPoll.objects.get().error_code, 'AUTOMATION_ACTOR_UNAUTHORIZED')
        self.admin.user_permissions.add(permission)
        self.enable(); self.profile.enabled = False; self.profile.save(update_fields=['enabled'])
        self.poll()
        self.assertFalse(Credential.objects.exists())

    def test_disable_before_poll_prevents_source_read(self):
        from .spreadsheet_automation import configure_automation
        self.enable()
        configure_automation(self.profile.pk, actor=self.admin, enabled=False)
        self.poll(side_effect=AssertionError('Disabled source read'))
        self.assertFalse(Credential.objects.exists())

    def test_disable_during_provider_read_prevents_row_commit(self):
        from .spreadsheet_automation import configure_automation
        self.enable()
        def read(profile):
            configure_automation(profile.pk, actor=self.other, enabled=False)
            return self.rows, digest(self.rows)
        self.poll(side_effect=read)
        self.assertFalse(Credential.objects.exists())

    def test_disable_between_rows_stops_next_row(self):
        from .spreadsheet_automation import configure_automation
        from .importers.preview import apply_award
        self.enable()
        self.rows.append([ROW[0], 'SYNTHETIC-SECOND', ROW[2], '2026-01-02', 'CONFIRMED'])
        def award(*args, **kwargs):
            result = apply_award(*args, **kwargs)
            configure_automation(self.profile.pk, actor=self.other, enabled=False)
            return result
        with patch('apps.integrations.importers.preview.apply_award', side_effect=award):
            self.poll()
        self.assertEqual(Credential.objects.count(), 1)

    def test_permission_revocation_between_rows_stops_next_row(self):
        from .importers.preview import apply_award
        self.enable()
        self.rows.append([ROW[0], 'SYNTHETIC-SECOND', ROW[2], '2026-01-02', 'CONFIRMED'])
        def award(*args, **kwargs):
            result = apply_award(*args, **kwargs)
            self.admin.user_permissions.clear()
            return result
        with patch('apps.integrations.importers.preview.apply_award', side_effect=award):
            self.poll()
        self.assertEqual(Credential.objects.count(), 1)

    def test_source_changes_between_snapshot_and_confirmation_fail_closed(self):
        self.enable()
        changed = grid([ROW[0], ROW[1], ROW[2], '2026-01-02', 'CONFIRMED'])
        calls = iter([(self.rows, digest(self.rows)), (changed, digest(changed))])
        self.poll(side_effect=lambda p: next(calls))
        self.assertFalse(Credential.objects.exists())
        from .models import SpreadsheetPoll
        self.assertEqual(SpreadsheetPoll.objects.get().error_code, 'SOURCE_CHANGED_REVIEW_REQUIRED')
        self.due(); self.poll()
        self.assertEqual(Credential.objects.count(), 1)

    def test_provider_outage_redacted_history_and_recovery(self):
        self.enable()
        self.poll(side_effect=SheetUnavailable('SECRET_PROVIDER_VALUE student@example.invalid'))
        from .models import SpreadsheetAutomation, SpreadsheetPoll
        self.assertEqual(SpreadsheetPoll.objects.get().error_code, 'GOOGLE_SOURCE_UNAVAILABLE')
        self.assertEqual(SpreadsheetAutomation.objects.get().source_sha256, '')
        response = self.client.get(f'{BASE}{self.profile.pk}/history/')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('SECRET_PROVIDER_VALUE', str(response.data))
        self.assertNotIn('student@example.invalid', str(response.data))
        self.assertNotIn('SYNTHETIC-CONTINUING-AUTHORITY', str(response.data))
        self.due(); self.poll()
        self.assertEqual(Credential.objects.count(), 1)
        self.assertTrue(SecurityAudit.objects.filter(actor=self.admin, action='SpreadsheetAutomaticPoll', status_code=200).exists())

    def test_concurrent_workers_claim_once_and_no_duplicate_issuance(self):
        from .spreadsheet_automation import poll_due_sources
        self.enable()
        barrier = Barrier(2)
        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                return poll_due_sources(limit=1)
            finally:
                close_old_connections()
        reader = lambda p: (self.rows, digest(self.rows))
        with patch('apps.integrations.spreadsheet_automation.read_profile_sheet', side_effect=reader), \
             patch('apps.integrations.importers.preview.read_profile_sheet', side_effect=reader):
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: worker(), range(2)))
        self.assertEqual(Credential.objects.count(), 1)
        self.assertEqual(SpreadsheetAward.objects.count(), 1)
        from .models import SpreadsheetPoll
        self.assertEqual(SpreadsheetPoll.objects.count(), 1)

    def test_expired_lease_recovery_and_stale_token_cannot_issue(self):
        from .models import SpreadsheetAutomation
        from .spreadsheet_automation import claim_source, require_automation_lease
        from .importers.preview import ImportProblem
        self.enable()
        binding, old_run = claim_source()
        SpreadsheetAutomation.objects.filter(pk=binding.pk).update(lease_until=timezone.now()-timedelta(seconds=1), next_poll_at=timezone.now())
        self.poll()
        self.assertEqual(Credential.objects.count(), 1)
        from django.db import transaction
        with transaction.atomic():
            with self.assertRaises(ImportProblem):
                require_automation_lease(binding.pk, old_run.lease_token, self.profile.pk, self.admin.pk)

    def test_poll_command_default_once_and_safe_sanitized_output(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('poll_spreadsheet_sources', stdout=out)
        self.assertNotIn('spreadsheet_id', out.getvalue())
        self.assertIn('checked', out.getvalue())

    def test_target_identity_and_range_drift_requires_explicit_reauthorization(self):
        from .models import SpreadsheetPoll
        for target in ({**TARGET, 'spreadsheet_id': 'SYNTHETIC_OTHER_SHEET'}, {**TARGET, 'range': 'A1:F20'}):
            self.enable()
            before = Credential.objects.count()
            with override_settings(BTU_SPREADSHEET_GOOGLE_SOURCES={'approved': target}):
                self.poll(side_effect=AssertionError('Changed target must not be read'))
                self.assertEqual(SpreadsheetPoll.objects.order_by('-started_at').first().error_code, 'AUTOMATION_SOURCE_CHANGED_REAUTHORIZE')
                self.assertEqual(Credential.objects.count(), before)
                self.enable()
                self.poll()
                self.assertEqual(Credential.objects.count(), 1)

    def test_target_drift_between_rows_blocks_later_row(self):
        from .importers.preview import apply_award
        self.enable()
        self.rows.append([ROW[0], 'SYNTHETIC-SECOND', ROW[2], '2026-01-02', 'CONFIRMED'])
        changed = override_settings(BTU_SPREADSHEET_GOOGLE_SOURCES={'approved': {**TARGET, 'range': 'A1:F20'}})
        def award(*args, **kwargs):
            result = apply_award(*args, **kwargs)
            changed.enable()
            return result
        try:
            with patch('apps.integrations.importers.preview.apply_award', side_effect=award):
                self.poll()
        finally:
            changed.disable()
        self.assertEqual(Credential.objects.count(), 1)

    def test_source_approval_and_actor_activation_rechecked_after_enable(self):
        self.enable()
        with override_settings(BTU_AUTHORIZED_COMPLETION_SOURCES=[]):
            self.poll(side_effect=AssertionError('Unauthorized source must not be read'))
        self.assertFalse(Credential.objects.exists())
        self.enable()
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        self.poll(side_effect=AssertionError('Inactive actor must not fetch'))
        self.assertFalse(Credential.objects.exists())

    def test_api_requires_import_grant_and_preserves_disabled_profile_controls(self):
        actor = User.objects.create_admin_user(email='readonly-automatic@btu.edu.ge',
            password=secrets.token_urlsafe(32), permission_codenames=['view_student_records'])
        self.client.force_authenticate(actor)
        for path in (BASE, f'{BASE}{self.profile.pk}/history/'):
            self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post(f'{BASE}{self.profile.pk}/', {'enabled':False}, format='json').status_code, 403)
        self.client.force_authenticate(None)
        self.assertIn(self.client.get(BASE).status_code, (401,403))
        self.client.force_authenticate(self.admin)
        self.enable(); self.profile.enabled=False; self.profile.save(update_fields=['enabled'])
        response=self.client.get(BASE)
        self.assertEqual(response.status_code,200)
        self.assertFalse(response.data['results'][0]['profile_enabled'])
        self.assertEqual(self.client.post(f'{BASE}{self.profile.pk}/',{'enabled':False},format='json').status_code,200)

    def test_stale_finish_never_overwrites_reclaimed_lease_or_history(self):
        from .models import SpreadsheetAutomation, SpreadsheetPoll
        from .spreadsheet_automation import _finish, claim_source
        self.enable()
        binding, old = claim_source()
        SpreadsheetAutomation.objects.filter(pk=binding.pk).update(lease_until=timezone.now()-timedelta(seconds=1),next_poll_at=timezone.now())
        binding2, new = claim_source()
        self.assertEqual(_finish(binding,old,state='COMPLETED',source_hash='a'*64,checkpoint=True),'FAILED')
        binding2.refresh_from_db(); old.refresh_from_db(); new.refresh_from_db()
        self.assertEqual(binding2.lease_token,new.lease_token)
        self.assertEqual(binding2.source_sha256,'')
        self.assertEqual(old.error_code,'AUTOMATION_LEASE_EXPIRED')
        self.assertEqual(new.state,'PROCESSING')

    def test_transient_failed_snapshot_recovers_same_attempt_budget(self):
        from .importers.preview import apply_award
        self.enable()
        with patch('apps.integrations.importers.preview.apply_award', side_effect=RuntimeError('SECRET failure')):
            self.poll()
        preview=SpreadsheetPreview.objects.get()
        self.assertEqual((preview.state,preview.attempts),('FAILED',1))
        self.assertFalse(Credential.objects.exists())
        self.due(); self.poll()
        preview.refresh_from_db()
        self.assertEqual((preview.state,preview.attempts),('COMPLETED',2))
        self.assertEqual(SpreadsheetPreview.objects.count(),1)
        self.assertEqual(Credential.objects.count(),1)

    def test_profile_fingerprint_is_pinned_and_policy_remains_database_immutable(self):
        from django.db import DatabaseError, transaction
        from .models import SpreadsheetAutomation
        from .spreadsheet_automation import approved_policy
        binding = self.enable()
        self.assertEqual(binding.approved_target_sha256, approved_policy(self.profile))
        with self.assertRaises(DatabaseError), transaction.atomic():
            type(self.profile).objects.filter(pk=self.profile.pk).update(
                approval_reference='SYNTHETIC-CHANGED-POLICY', definition_sha256='a'*64)
        self.profile.refresh_from_db()
        self.assertEqual(SpreadsheetAutomation.objects.get().approved_target_sha256, approved_policy(self.profile))
        self.assertFalse(Credential.objects.exists())

    def test_concurrent_stale_completion_and_reclaim_do_not_deadlock_or_checkpoint(self):
        from django.db import connection
        from .models import SpreadsheetAutomation, SpreadsheetPoll
        from .spreadsheet_automation import _finish, claim_source
        self.enable()
        old_binding, old = claim_source()
        SpreadsheetAutomation.objects.filter(pk=old_binding.pk).update(
            lease_until=timezone.now()-timedelta(seconds=1), next_poll_at=timezone.now())
        barrier = Barrier(2)
        def worker(finish):
            close_old_connections()
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
                barrier.wait(timeout=20)
                return (_finish(old_binding, old, state='COMPLETED', source_hash='a'*64, checkpoint=True)
                        if finish else claim_source())
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, True), pool.submit(worker, False)]
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual(results[0], 'FAILED')
        old.refresh_from_db()
        self.assertEqual(old.state, 'FAILED')
        binding = SpreadsheetAutomation.objects.get()
        self.assertEqual(binding.source_sha256, '')
        self.assertEqual(SpreadsheetPoll.objects.filter(state='COMPLETED').count(), 0)
