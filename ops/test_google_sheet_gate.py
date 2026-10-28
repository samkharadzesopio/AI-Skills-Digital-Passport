"""Approval guards without Django, a database, valid credentials or Google calls."""
from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import run_isolated_tests
from test_google_sheets_e2e import arguments


class GoogleApprovalGateTests(unittest.TestCase):
    def test_default_never_selects_live_google(self):
        self.assertIsNone(arguments([]))

    def test_both_live_flags_required_before_config_file_access(self):
        with patch.object(Path, 'stat', side_effect=AssertionError('Must not inspect a live file')):
            for args in (['--allow-google-read'], ['--live-config', 'PRIVATE_PATH']):
                with self.subTest(args=args), redirect_stderr(StringIO()), self.assertRaises(SystemExit) as result:
                    arguments(args)
                self.assertEqual(result.exception.code, 2)

    def test_opted_in_configuration_validation_does_not_parse_credentials(self):
        with tempfile.TemporaryDirectory(prefix='synthetic-google-gate-') as directory:
            path = Path(directory)
            key = path / 'synthetic-not-a-key.json'
            key.write_text('SYNTHETIC INVALID KEY: must not be parsed or used')
            config = {'target': {'spreadsheet_id': 'SYNTHETIC_APPROVED_ID', 'worksheet': 'Passport Skill Records', 'range': 'A1:F20'},
                      'unshared_spreadsheet_id': 'SYNTHETIC_UNSHARED_ID', 'credential_file': str(key),
                      'approval_reference': 'SYNTHETIC-LOCAL-ONLY'}
            manifest = path / 'manifest.json'
            manifest.write_text(json.dumps(config))
            self.assertEqual(arguments(['--live-config', str(manifest), '--allow-google-read']), config)
            config['target']['range'] = 'A:F'
            manifest.write_text(json.dumps(config))
            error = StringIO()
            with redirect_stderr(error), self.assertRaises(SystemExit) as result:
                arguments(['--live-config', str(manifest), '--allow-google-read'])
            self.assertEqual(result.exception.code, 2)
            self.assertNotIn(str(key), error.getvalue())

    def test_outer_runner_rejects_partial_approval_before_allocating_resources(self):
        for args in (['--allow-google-read'], ['--google-sheet-live', 'PRIVATE_PATH'], ['--google-sheet-live']):
            with self.subTest(args=args), patch.object(sys, 'argv', ['runner', *args]):
                with patch.object(run_isolated_tests, 'DisposableRun', side_effect=AssertionError('No resources authorized')):
                    with self.assertRaises(SystemExit):
                        run_isolated_tests.main()


if __name__ == '__main__':
    unittest.main()
