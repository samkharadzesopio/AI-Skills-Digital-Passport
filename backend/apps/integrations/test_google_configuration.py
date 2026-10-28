"""Local configuration and failure regressions; these never authenticate to Google."""
from io import StringIO
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from config.spreadsheet_sources import credential_path, validate_sources, validate_target
from .importers.sheet_source import SheetUnavailable, read_profile_sheet

TARGET = {'spreadsheet_id': 'SYNTHETIC_SHEET_ID', 'worksheet': 'Passport Skill Records', 'range': 'A1:F20'}
PROFILE = SimpleNamespace(definition={'google_source': 'approved', 'worksheet': TARGET['worksheet']})


class GoogleConfigurationTests(SimpleTestCase):
    def test_bounded_ranges_and_legacy_configuration(self):
        self.assertEqual(validate_target(TARGET), 'A1:F20')
        self.assertEqual(validate_target({k: v for k, v in TARGET.items() if k != 'range'}), 'A1:Z5011')
        for area in ('A:F', 'A1:AA20', 'A2:F20', 'B1:F20', 'A1:F5012', 'A1:F0', 'A1:F99999',
                     'Other!A1:F20', 'named_range', '=IMPORTDATA("url")', 20, None):
            with self.subTest(area=area), self.assertRaises(ValueError):
                validate_target({**TARGET, 'range': area})
        for sources in ([], {'bad key': TARGET}, {'approved': {**TARGET, 'url': 'ignored'}},
                        {'approved': {**TARGET, 'spreadsheet_id': 'https://example.test/'}}):
            with self.subTest(sources=sources), self.assertRaises(ValueError):
                validate_sources(sources)

    def test_credential_paths_require_absolute_file_outside_git_including_worktree_markers(self):
        with tempfile.TemporaryDirectory(prefix='synthetic-google-location-') as directory:
            base = Path(directory)
            path = base / 'synthetic.json'
            path.write_text('{}')
            self.assertEqual(credential_path(str(path)), path.resolve())
            (base / '.git').write_text('synthetic worktree marker')
            with self.assertRaises(ValueError):
                credential_path(str(path))
        for value in ('relative.json', '', None):
            with self.assertRaises(ValueError):
                credential_path(value)

    @override_settings(BTU_SPREADSHEET_GOOGLE_SOURCES={'approved': TARGET})
    def test_exact_target_range_and_target_change_digest_binding(self):
        client = MagicMock()
        worksheet = client.open_by_key.return_value.worksheet.return_value
        worksheet.get.return_value = [['Synthetic']]
        _, first = read_profile_sheet(PROFILE, client=client)
        client.open_by_key.assert_called_once_with(TARGET['spreadsheet_id'])
        client.open_by_key.return_value.worksheet.assert_called_once_with(TARGET['worksheet'])
        worksheet.get.assert_called_once_with('A1:F20', value_render_option='FORMULA')
        with override_settings(BTU_SPREADSHEET_GOOGLE_SOURCES={'approved': {**TARGET, 'range': 'A1:F21'}}):
            _, second = read_profile_sheet(PROFILE, client=client)
        self.assertNotEqual(first, second)

    def test_invalid_target_is_rejected_before_google_client_creation(self):
        with override_settings(BTU_SPREADSHEET_GOOGLE_SOURCES={'approved': {**TARGET, 'range': 'A:F'}}):
            with patch('gspread.service_account') as factory, self.assertRaises(SheetUnavailable):
                read_profile_sheet(PROFILE)
            factory.assert_not_called()

    @override_settings(BTU_SPREADSHEET_GOOGLE_SOURCES={'approved': TARGET})
    @patch('apps.integrations.importers.sheet_source.time.sleep')
    def test_quota_retry_is_bounded_and_permission_denial_not_retried(self, sleep):
        for status, attempts in ((429, 3), (503, 3), (403, 1), (404, 1)):
            with self.subTest(status=status):
                client = MagicMock()
                error = requests.HTTPError('PRIVATE_PROVIDER_DETAIL')
                error.response = SimpleNamespace(status_code=status)
                client.open_by_key.side_effect = error
                with self.assertRaises(SheetUnavailable) as result:
                    read_profile_sheet(PROFILE, client=client)
                self.assertNotIn('PRIVATE', str(result.exception))
                self.assertEqual(client.open_by_key.call_count, attempts)

    def test_operator_read_command_requires_approval_before_database_or_network(self):
        with patch('gspread.service_account') as factory:
            with self.assertRaisesMessage(CommandError, 'No Google request made'):
                call_command('check_google_sheet', profile_id='not-read', approval_reference='synthetic', stdout=StringIO())
            factory.assert_not_called()
