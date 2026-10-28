"""Synthetic workbook shape and real PostgreSQL domain/authorization regressions."""
import copy
import io
import json
import secrets
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import MagicMock, patch

import requests
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from openpyxl import Workbook
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.credentials.models import Credential
from apps.credentials.test_support import create_test_issuer
from apps.integrations.models import ImportRun, SpreadsheetAward, SpreadsheetPreview
from apps.passports.models import DigitalPassport, PassportVersion
from apps.skills.models import Skill, VerifiedAchievement
from apps.students.models import Student
from .importers.mapping import digest, excel_grid, map_grid, validate_definition
from .importers.preview import ImportProblem, confirm_preview, create_preview
from .importers.profiles import provision_profile
from .importers.sheet_source import SheetUnavailable, read_profile_sheet
from .importers.validators import ImportValidationError, REQUIRED_FIELDS


def definition():
    return {'worksheet': 'Passport Skill Records', 'evidence_namespace': 'synthetic-approved-awards',
            'columns': {'external_student_id': ['Student ID'], 'source_event_id': ['Record ID'],
                        'skill_code': ['Skill ID'], 'earned_on': ['Date Earned'],
                        'approval_status': ['Institutional Approval']},
            'allowed_skill_codes': ['SYNTHETIC-SKILL'], 'eligible_student_statuses': ['ACTIVE']}


HEADERS = ['Student ID', 'Record ID', 'Skill ID', 'Date Earned', 'Institutional Approval']
ROW = ['SYNTHETIC-STUDENT', 'SYNTHETIC-RECORD', 'SYNTHETIC-SKILL', '2026-01-01', 'CONFIRMED']


def grid(*rows):
    return [['Synthetic workbook'], [], [], HEADERS, *rows]


def workbook(rows):
    book = Workbook()
    book.active.title = 'Passport Skill Records'
    for row in rows:
        book.active.append(row)
    data = io.BytesIO()
    book.save(data)
    book.close()
    data.seek(0)
    return data


class MappingTests(SimpleTestCase):
    def test_row_four_aliases_separators_whitespace_reorder_extra_columns(self):
        d = definition()
        rows = [['Metadata'], [], [], [' DATE_EARNED ', 'RECORD-ID', 'skill/id', 'student.id', 'Institutional Approval', 'ignored'],
                ['2026-01-01', ' R1 ', 'SYNTHETIC-SKILL', ' STUDENT1 ', 'CONFIRMED', '=DO_NOT_EXECUTE()']]
        mapped = map_grid(rows, kind='SKILL_AWARD', definition=d)
        self.assertEqual(mapped['header_row'], 4)
        self.assertEqual(mapped['records'][0]['record']['external_student_id'], 'STUDENT1')

    def test_ambiguous_headers_and_aliases_fail(self):
        for rows in ([HEADERS + ['Student ID'], ROW], [HEADERS, HEADERS, ROW]):
            with self.assertRaises(ImportValidationError):
                map_grid(rows, kind='SKILL_AWARD', definition=definition())
        d = definition()
        d['columns']['skill_code'].append(' student_id ')
        with self.assertRaises(ImportValidationError):
            validate_definition('SKILL_AWARD', d)

    def test_system_outputs_cannot_be_approval_aliases(self):
        for label in ['Passport Sync Status', 'Synced Passport Version', 'Synced At (UTC)', 'Passport ID (Existing)']:
            d = definition()
            d['columns']['approval_status'] = [label]
            with self.assertRaises(ImportValidationError):
                validate_definition('SKILL_AWARD', d)

    def test_missing_fields_and_header_detection_bound(self):
        for rows in ([HEADERS[:-2], ROW], [[]] * 10 + [HEADERS, ROW]):
            with self.assertRaises(ImportValidationError):
                map_grid(rows, kind='SKILL_AWARD', definition=definition())

    def test_skill_identifier_value_mapping_is_exact_not_separator_or_case_guessing(self):
        d = definition()
        d['value_maps'] = {'skill_code': {'APPROVED-EXTERNAL-ID': 'SYNTHETIC-SKILL'}}
        for external in ('approved-external-id', 'APPROVED_EXTERNAL_ID'):
            result = map_grid(grid([ROW[0], ROW[1], external, *ROW[3:]]), kind='SKILL_AWARD', definition=d)
            self.assertEqual(result['issues'][0]['code'], 'SKILL_NOT_AUTHORIZED')
        result = map_grid(grid([ROW[0], ROW[1], 'APPROVED-EXTERNAL-ID', *ROW[3:]]), kind='SKILL_AWARD', definition=d)
        self.assertEqual(result['records'][0]['record']['skill_code'], 'SYNTHETIC-SKILL')

    def test_invalid_ambiguous_and_future_dates(self):
        d = definition()
        d['date_formats'] = ['%d/%m/%Y', '%m/%d/%Y']
        for value in ['31/02/2026', '01/02/2026', '01/01/2999', 46000]:
            mapped = map_grid(grid([*ROW[:3], value, ROW[4]]), kind='SKILL_AWARD', definition=d)
            self.assertEqual(len(mapped['issues']), 1)

    def test_formulas_mapped_fail_ignored_formulas_remain_unexecuted(self):
        file = workbook(grid([*ROW[:3], '=NOW()', 'CONFIRMED']))
        rows, _ = excel_grid(file, worksheet='Passport Skill Records')
        result = map_grid(rows, kind='SKILL_AWARD', definition=definition())
        self.assertEqual(result['issues'][0]['code'], 'FORMULA_NOT_ALLOWED')

    def test_blank_rows_partial_records_and_date_cells(self):
        rows = grid(ROW, [], ['ID-ONLY'], [*ROW[:3], timezone.now().date(), 'PENDING'])
        file = workbook(rows)
        parsed, _ = excel_grid(file, worksheet='Passport Skill Records')
        mapped = map_grid(parsed, kind='SKILL_AWARD', definition=definition())
        self.assertEqual((len(mapped['records']), len(mapped['issues']), mapped['total_rows']), (2, 1, 3))

    def test_file_size_malformed_zip_column_and_row_bounds(self):
        for file in (io.BytesIO(b'bad file'), io.BytesIO(b'x' * (5 * 1024 * 1024 + 1)), workbook([['x'] * 27])):
            with self.assertRaises(ImportValidationError):
                excel_grid(file, worksheet='Passport Skill Records')
        with self.assertRaises(ImportValidationError):
            map_grid([HEADERS] + [ROW] * 5001, kind='SKILL_AWARD', definition=definition())

    def test_completion_mapping_reuses_strict_validator(self):
        d = {'columns': {f: [f] for f in REQUIRED_FIELDS}}
        values = ['STUDENT', 'AI-101', 'completed', '90', 'true', '2026-01-01', 'EVENT']
        result = map_grid([list(REQUIRED_FIELDS), values], kind='COMPLETION', definition=d)
        self.assertEqual(result['records'][0]['record']['grade'], 90.0)
        self.assertTrue(result['records'][0]['record']['passed'])
        values[2] = 'pending'
        self.assertEqual(len(map_grid([list(REQUIRED_FIELDS), values], kind='COMPLETION', definition=d)['issues']), 1)


@override_settings(BTU_CLASSROOM_ISSUER_REFERENCE='BTU-UNIVERSITY', BTU_AUTHORIZED_COMPLETION_SOURCES=['BTU_EXCEL', 'BTU_GOOGLE_SHEETS'])
class SpreadsheetDomainTests(TransactionTestCase):
    def setUp(self):
        self.admin = User.objects.create_admin_user(email='spreadsheet-admin@btu.edu.ge', password=secrets.token_urlsafe(32), permission_codenames=['import_completions'])
        self.other = User.objects.create_admin_user(email='other-importer@btu.edu.ge', password=secrets.token_urlsafe(32), permission_codenames=['import_completions'])
        self.student = Student.objects.create(external_student_id=ROW[0], first_name='Synthetic', last_name='Student',
            email='spreadsheet-student@btu.edu.ge', program='AI', education_level='Bachelor', student_status='ACTIVE')
        self.skill = Skill.objects.create(skill_code=ROW[2], skill_name='Synthetic skill', category='AI Skill',
            description='Synthetic catalog', stamp_type='FOCUSED', badge_asset_id='synthetic')
        create_test_issuer('Synthetic BTU')
        self.profile = self.make_profile()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def make_profile(self, **changes):
        manifest = {'key': 'synthetic-source', 'version': 1, 'source': 'BTU_EXCEL', 'kind': 'SKILL_AWARD',
                    'approval_reference': 'SYNTHETIC-POLICY-APPROVAL', 'definition': definition(), **changes}
        profile = provision_profile(manifest)
        profile.enabled = True
        profile.save(update_fields=['enabled'])
        return profile

    def preview(self, rows=None, profile=None):
        rows = rows or grid(ROW)
        return create_preview(profile or self.profile, rows, digest(rows), actor=self.admin)

    def confirm(self, preview):
        return confirm_preview(preview.pk, preview.snapshot_sha256, actor=self.admin)

    def test_preview_never_awards_then_confirmation_uses_real_domains(self):
        preview = self.preview()
        self.assertEqual(preview.report['valid_records'], 1)
        self.assertEqual((Credential.objects.count(), VerifiedAchievement.objects.count(), DigitalPassport.objects.count()), (0, 0, 0))
        result = self.confirm(preview)
        self.assertEqual(result.run.summary['issued'], 1)
        receipt = SpreadsheetAward.objects.get()
        self.assertEqual(receipt.achievement_event.course_id, '')
        self.assertEqual(receipt.credential.achievements.get().student_id, self.student.pk)
        self.assertEqual(PassportVersion.objects.count(), 1)
        self.assertEqual(self.confirm(preview).run_id, result.run_id)
        self.assertEqual(Credential.objects.count(), 1)

    def test_pending_rejected_missing_approval_never_issue(self):
        rows = grid([*ROW[:4], 'PENDING'], [ROW[0], 'R2', *ROW[2:4], 'REJECTED'], [ROW[0], 'R3', *ROW[2:4], ''])
        p = self.preview(rows)
        self.assertEqual(p.report['review_records'], 3)
        with self.assertRaises(ImportProblem):
            self.confirm(p)
        self.assertFalse(Credential.objects.exists())

    def test_workbook_shape_without_approval_reports_review(self):
        headers = ['Student ID', 'First Name', 'Last Name', 'BTU Email (Test)', 'Program', 'Education Level',
            'Passport ID (Existing)', 'First Issued (Existing)', 'Student Status', 'Record ID', 'Skill ID',
            'Skill Name', 'Skill Category', 'Badge/Stamp Code', 'Skill Description', 'Date Earned',
            'Passport Sync Status', 'Synced Passport Version', 'Synced At (UTC)', 'Sync Error / Notes']
        values = [ROW[0], 'Synthetic', 'Student', 'student@btu.edu.ge', 'AI', 'Bachelor', 'IGNORED', '', 'ACTIVE',
            ROW[1], ROW[2], 'Synthetic skill', 'AI Skill', '=IF(1,2,3)', 'Synthetic', ROW[3], 'SYNCED', 'v99', '', '']
        p = self.preview([['Synthetic metadata'], [], [], headers, values, [ROW[0]]])
        self.assertEqual((p.report['review_records'], p.report['invalid_records']), (1, 1))
        self.assertFalse(DigitalPassport.objects.exists())

    def test_duplicate_and_conflicting_records_all_conflicts_blocked(self):
        p = self.preview(grid(ROW, ROW))
        self.assertEqual((p.report['valid_records'], p.report['duplicate_records']), (1, 1))
        self.confirm(p)
        self.assertEqual(self.preview().report['duplicate_records'], 1)
        changed = [*ROW[:3], '2026-01-02', 'CONFIRMED']
        p = self.preview(grid(ROW, changed))
        self.assertEqual(p.report['invalid_records'], 2)
        self.assertEqual(self.preview(grid(changed)).report['rows'][0]['code'], 'EVIDENCE_PAYLOAD_CONFLICT')

    def test_invalid_duplicate_cannot_leave_the_other_copy_eligible(self):
        p = self.preview(grid(ROW, [*ROW[:3], 'bad date', 'CONFIRMED']))
        self.assertEqual((p.report['valid_records'], p.report['invalid_records']), (0, 2))

    def test_concurrent_confirmations_and_durable_replay_issue_once(self):
        p = self.preview()
        barrier = Barrier(2)
        def run(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return confirm_preview(p.pk, p.snapshot_sha256, actor=self.admin).state
                except ImportProblem as exc:
                    return exc.code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(run, range(2)))
        self.assertIn('COMPLETED', outcomes)
        self.assertEqual((Credential.objects.count(), SpreadsheetAward.objects.count()), (1, 1))
        self.assertEqual(self.confirm(p).state, 'COMPLETED')

    def test_cancelled_passport_never_reactivated_by_new_evidence(self):
        self.confirm(self.preview())
        from apps.passports.lifecycle import revoke_passport
        registrar = User.objects.create_admin_user(email='lifecycle-import-test@btu.edu.ge', password=secrets.token_urlsafe(32), permission_codenames=['manage_passport_lifecycle'])
        passport = DigitalPassport.objects.get(student=self.student)
        revoke_passport(actor=registrar, passport_reference=passport.public_reference, idempotency_key='SYNTHETIC-REVOCATION', reason='Synthetic test')
        p = self.preview(grid([ROW[0], 'NEW-RECORD', *ROW[2:]]))
        self.assertEqual(p.report['rows'][0]['code'], 'CANCELLED_PASSPORT_REQUIRES_REPLACEMENT')
        with self.assertRaises(ImportProblem):
            self.confirm(p)
        self.assertEqual(DigitalPassport.objects.count(), 1)
        self.assertFalse(DigitalPassport.objects.filter(status='ACTIVE').exists())

    def test_unknown_catalog_and_conflicting_student_metadata(self):
        d = definition()
        d['columns']['first_name'] = ['First Name']
        p = self.make_profile(key='identity-check', definition=d)
        preview = self.preview([HEADERS + ['First Name'], ROW + ['Wrong identity']], profile=p)
        self.assertEqual(preview.report['rows'][0]['code'], 'STUDENT_IDENTITY_CONFLICT')
        self.skill.delete()
        self.assertEqual(self.preview().report['rows'][0]['code'], 'UNKNOWN_SKILL')

    def test_flexible_completions_issue_with_existing_catalog_and_replay_strict_history(self):
        for code in ('AI_LITERACY', 'AI_FUNDAMENTALS'):
            Skill.objects.create(skill_code=code, skill_name=code, category='AI', description='Synthetic', stamp_type='FOCUSED', badge_asset_id='synthetic')
        profile = self.make_profile(key='completions', kind='COMPLETION', definition={'columns': {k: [k] for k in REQUIRED_FIELDS}})
        values = [ROW[0], 'AI-101', 'completed', '90', True, '2026-01-01', 'SHARED-COMPLETION']
        p = self.preview([list(REQUIRED_FIELDS), values], profile=profile)
        self.assertEqual(self.confirm(p).run.summary['issued'], 1)
        self.assertEqual(self.preview([list(REQUIRED_FIELDS), values], profile=profile).report['duplicate_records'], 1)
        self.assertEqual(Credential.objects.count(), 1)
        self.assertEqual(ImportRun.objects.count(), 1)

    def test_flexible_completion_cannot_ignore_a_pending_approval_column(self):
        columns = {k: [k] for k in REQUIRED_FIELDS}
        columns['approval_status'] = ['Approval']
        profile = self.make_profile(key='pending-completion', kind='COMPLETION', definition={'columns': columns})
        values = [ROW[0], 'AI-101', 'completed', 90, True, '2026-01-01', 'PENDING-COMPLETION', 'PENDING']
        p = self.preview([list(REQUIRED_FIELDS) + ['Approval'], values], profile=profile)
        self.assertEqual((p.report['valid_records'], p.report['review_records']), (0, 1))
        self.assertFalse(Credential.objects.exists())

    def test_cross_profile_version_and_cross_channel_do_not_duplicate_award(self):
        self.confirm(self.preview())
        d = definition()
        d['google_source'] = 'synthetic-approved-sheet'
        other = self.make_profile(key='other-profile', version=2, source='BTU_GOOGLE_SHEETS', definition=d)
        self.assertEqual(self.preview(profile=other).report['duplicate_records'], 1)
        self.assertEqual(Credential.objects.count(), 1)

    def test_student_skill_and_identity_failures(self):
        self.student.student_status = 'INACTIVE'
        self.student.save()
        self.assertEqual(self.preview().report['rows'][0]['code'], 'STUDENT_NOT_ELIGIBLE')
        self.student.delete()
        self.assertEqual(self.preview().report['rows'][0]['code'], 'UNKNOWN_STUDENT')

    def test_changed_identity_or_catalog_revalidated_after_review(self):
        p = self.preview()
        self.skill.delete()
        self.assertEqual(self.confirm(p).run.summary['failed'], 1)
        self.assertFalse(Credential.objects.exists())

    def test_atomic_failure_retry_preserves_no_partial_awards(self):
        p = self.preview()
        with patch('apps.integrations.importers.preview.issue_credential', side_effect=RuntimeError('private details')):
            result = self.confirm(p)
        self.assertEqual(result.state, 'FAILED')
        self.assertEqual(VerifiedAchievement.objects.count(), 0)
        self.assertNotIn('private details', str(result.run.summary))
        self.assertEqual(self.confirm(p).run.summary['issued'], 1)

    def test_process_crash_after_committed_row_resumes_without_duplicate_issuance(self):
        from .importers.preview import apply_award
        p = self.preview(grid(ROW, [ROW[0], 'SECOND-RECORD', *ROW[2:]]))
        calls = [0]
        def interrupt(*args, **kwargs):
            calls[0] += 1
            if calls[0] == 2:
                raise KeyboardInterrupt('Synthetic crash after first committed row')
            return apply_award(*args, **kwargs)
        with patch('apps.integrations.importers.preview.apply_award', side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.confirm(p)
        self.assertEqual(Credential.objects.count(), 1)
        p.refresh_from_db()
        self.assertEqual(p.state, 'PROCESSING')
        p.lease_until = timezone.now() - timedelta(seconds=1)
        p.save(update_fields=['lease_until'])
        result = self.confirm(p).run.summary
        self.assertEqual((result['issued'], result['skipped']), (1, 1))
        self.assertEqual(Credential.objects.count(), 2)

    def test_reversing_integrity_migration_refuses_reviewed_history(self):
        self.preview()
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor
        leaves = MigrationExecutor(connection).loader.graph.leaf_nodes()
        try:
            with self.assertRaises(RuntimeError):
                MigrationExecutor(connection).migrate([('integrations', '0003_spreadsheetprofile_spreadsheetpreview_and_more')])
        finally:
            MigrationExecutor(connection).migrate(leaves)

    def test_digest_expiry_lease_and_crash_recovery(self):
        p = self.preview()
        with self.assertRaises(ImportProblem):
            confirm_preview(p.pk, '0' * 64, actor=self.admin)
        with patch('apps.integrations.importers.preview.timezone.now', return_value=timezone.now() + timedelta(hours=2)):
            with self.assertRaises(ImportProblem):
                self.confirm(p)
        p.state, p.lease_until = 'PROCESSING', timezone.now() + timedelta(minutes=5)
        p.save(update_fields=['state', 'lease_until'])
        with self.assertRaises(ImportProblem):
            self.confirm(p)
        p.lease_until = timezone.now() - timedelta(seconds=1)
        p.save(update_fields=['lease_until'])
        self.assertEqual(self.confirm(p).run.summary['issued'], 1)

    def test_policy_disable_and_channel_revocation(self):
        p = self.preview()
        self.profile.enabled = False
        self.profile.save(update_fields=['enabled'])
        with self.assertRaises(ImportProblem):
            self.confirm(p)
        self.profile.enabled = True
        self.profile.save(update_fields=['enabled'])
        with override_settings(BTU_AUTHORIZED_COMPLETION_SOURCES=[]):
            with self.assertRaises(ImportProblem):
                self.confirm(p)

    def test_reviewed_inputs_profiles_and_receipts_are_database_immutable(self):
        p = self.preview()
        for model, pk, values in [(type(p), p.pk, {'records': []}), (type(self.profile), self.profile.pk, {'definition': {}})]:
            with self.assertRaises(DatabaseError), transaction.atomic():
                model.objects.filter(pk=pk).update(**values)
        self.confirm(p)
        with self.assertRaises(DatabaseError), transaction.atomic():
            SpreadsheetAward.objects.update(payload={})

    def test_authorized_api_preview_confirmation_and_private_ownership(self):
        uploaded = SimpleUploadedFile('synthetic.xlsx', workbook(grid(ROW)).read())
        response = self.client.post('/api/integrations/import/excel/', {'profile_id': str(self.profile.pk), 'file': uploaded}, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        data = response.json()
        self.assertNotIn(ROW[0], str(data))
        self.assertEqual(response['Cache-Control'], 'no-store')
        path = f"/api/integrations/import/previews/{data['id']}/"
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(path).status_code, 404)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(path + 'confirm/', {'confirm': True, 'snapshot_sha256': data['snapshot_sha256']}, format='json').status_code, 200)
        self.assertEqual(Credential.objects.count(), 1)

    def test_permission_and_csrf_not_bypassed(self):
        unprivileged = User.objects.create_admin_user(email='no-import@btu.edu.ge', password=secrets.token_urlsafe(32), permission_codenames=['view_student_records'])
        self.client.force_authenticate(unprivileged)
        self.assertEqual(self.client.get('/api/integrations/import/profiles/').status_code, 403)
        with self.assertRaises(Exception):
            create_preview(self.profile, grid(ROW), digest(ROW), actor=unprivileged)
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.admin, backend='apps.accounts.authentication.AdminPasswordBackend')
        self.assertEqual(client.post('/api/integrations/import/google-sheets/preview/', {'profile_id': str(self.profile.pk)}, format='json').status_code, 403)

    def test_google_changed_snapshot_and_arbitrary_targets_rejected(self):
        d = definition()
        d['google_source'] = 'synthetic-sheet'
        profile = self.make_profile(key='google', source='BTU_GOOGLE_SHEETS', definition=d)
        p = self.preview(profile=profile)
        with patch('apps.integrations.importers.preview.read_profile_sheet', return_value=(grid(ROW), '0' * 64)):
            with self.assertRaises(ImportProblem):
                self.confirm(p)
        response = self.client.post('/api/integrations/import/google-sheets/preview/', {'profile_id': str(profile.pk), 'spreadsheet_id': 'arbitrary'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Credential.objects.exists())

    def test_google_provider_fixture_uses_shared_preview_validation_and_real_issuance(self):
        d = definition()
        d['google_source'] = 'approved-sheet'
        profile = self.make_profile(key='google-approved', source='BTU_GOOGLE_SHEETS', definition=d)
        provider = MagicMock()
        provider.open_by_key.return_value.worksheet.return_value.get.return_value = grid(ROW)
        with tempfile.TemporaryDirectory(prefix='synthetic-google-key-') as directory:
            path = Path(directory) / 'not-a-real-key.json'
            path.write_text('{}')
            self._google_provider_workflow(profile, provider, path)
        self.assertEqual(Credential.objects.count(), 1)

    def test_operator_google_diagnostic_is_read_only_and_honors_profile_approval(self):
        profile = self.make_profile(key='google-diagnostic', source='BTU_GOOGLE_SHEETS',
                                    definition={**definition(), 'google_source': 'approved'})
        output = io.StringIO()
        reader = 'apps.integrations.management.commands.check_google_sheet.read_profile_sheet'
        with patch(reader, return_value=(grid(ROW), 'a' * 64)) as read:
            with CaptureQueriesContext(connection) as queries:
                call_command('check_google_sheet', profile_id=str(profile.pk),
                    approval_reference=profile.approval_reference, allow_google_read=True, stdout=output)
            read.assert_called_once()
        self.assertEqual(json.loads(output.getvalue())['google_read'], 'PASS')
        self.assertFalse(json.loads(output.getvalue())['imported'])
        self.assertFalse(any(q['sql'].lstrip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'ALTER', 'CREATE', 'DROP')) for q in queries))
        self.assertEqual(Credential.objects.count(), 0)
        with patch(reader) as read:
            with self.assertRaises(CommandError):
                call_command('check_google_sheet', profile_id=str(profile.pk),
                    approval_reference='NOT-APPROVED', allow_google_read=True, stdout=io.StringIO())
            read.assert_not_called()
        with patch(reader, side_effect=RuntimeError('PRIVATE_GOOGLE_DETAIL')):
            with self.assertRaises(CommandError) as result:
                call_command('check_google_sheet', profile_id=str(profile.pk),
                    approval_reference=profile.approval_reference, allow_google_read=True, stdout=io.StringIO())
            self.assertNotIn('PRIVATE_GOOGLE_DETAIL', str(result.exception))

    def _google_provider_workflow(self, profile, provider, path):
        with override_settings(GOOGLE_SERVICE_ACCOUNT_FILE=str(path), BTU_SPREADSHEET_GOOGLE_SOURCES={
            'approved-sheet': {'spreadsheet_id': 'SYNTHETIC_SHEET_ID', 'worksheet': 'Passport Skill Records'}}):
            with patch('gspread.service_account', return_value=provider) as factory:
                response = self.client.post('/api/integrations/import/google-sheets/preview/', {'profile_id': str(profile.pk)}, format='json')
                self.assertEqual(response.status_code, 201, response.data)
                data = response.json()
                self.assertEqual(Credential.objects.count(), 0)
                response = self.client.post(f"/api/integrations/import/previews/{data['id']}/confirm/", {
                    'confirm': True, 'snapshot_sha256': data['snapshot_sha256']}, format='json')
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.json()['result']['issued'], 1)
                self.assertEqual(factory.call_args.kwargs['scopes'], ['https://www.googleapis.com/auth/spreadsheets.readonly'])
                self.assertEqual(provider.open_by_key.call_count, 2)


@override_settings(BTU_SPREADSHEET_GOOGLE_SOURCES={'approved': {'spreadsheet_id': 'SYNTHETIC_SHEET_ID', 'worksheet': 'Passport Skill Records'}})
class SheetReaderTests(SimpleTestCase):
    def setUp(self):
        self.profile = MagicMock()
        self.profile.definition = {**definition(), 'google_source': 'approved'}
        self.client = MagicMock()
        self.worksheet = self.client.open_by_key.return_value.worksheet.return_value
        self.worksheet.get.return_value = grid(ROW)

    def test_configured_range_read_only_and_stable_snapshot(self):
        rows, hashed = read_profile_sheet(self.profile, client=self.client)
        self.client.set_timeout.assert_called_once_with((5, 10))
        self.worksheet.get.assert_called_once_with('A1:Z5011', value_render_option='FORMULA')
        self.assertEqual(len(rows), 5)
        self.assertEqual(len(hashed), 64)

    @patch('apps.integrations.importers.sheet_source.time.sleep')
    def test_transient_api_errors_bounded_retry_and_safe_failure(self, sleep):
        self.worksheet.get.side_effect = requests.Timeout('private provider detail')
        with self.assertRaises(SheetUnavailable) as error:
            read_profile_sheet(self.profile, client=self.client)
        self.assertEqual(self.worksheet.get.call_count, 3)
        self.assertNotIn('private', str(error.exception))

    def test_missing_credentials_source_and_unauthorized_errors(self):
        with override_settings(GOOGLE_SERVICE_ACCOUNT_FILE=''):
            with self.assertRaises(SheetUnavailable):
                read_profile_sheet(self.profile)
        self.profile.definition['google_source'] = 'unknown'
        with self.assertRaises(SheetUnavailable):
            read_profile_sheet(self.profile, client=self.client)
