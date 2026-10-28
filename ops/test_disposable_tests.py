"""No shared DB or application settings are loaded by these regressions."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from disposable_tests import DisposableRun, test_database_name
from run_isolated_tests import child_console_flags
from manual_demo import control_session


class CleanupTests(unittest.TestCase):
    def test_windows_manual_child_inherits_console(self):
        with patch('run_isolated_tests.os.name', 'nt'), patch.object(subprocess, 'CREATE_NO_WINDOW', 0x08000000, create=True):
            self.assertEqual(child_console_flags(interactive=True), {})
            self.assertEqual(child_console_flags(), {'creationflags': 0x08000000})

    def test_demo_controller_refuses_nonsynthetic_fixture_before_login(self):
        import json
        with tempfile.TemporaryDirectory(prefix='btu-live-browser-private-') as directory:
            path = Path(directory) / 'preview-private.json'
            path.write_text(json.dumps({'adminEmail': 'browser.admin@btu.edu.ge',
                                        'studentEmail': 'browser.student@btu.edu.ge'}))
            path.with_name('preview-runtime.json').write_text('{"synthetic": false}')
            with patch('manual_demo.DemoClient.request', side_effect=AssertionError('No HTTP')):
                with self.assertRaisesRegex(ValueError, 'Synthetic fixture'):
                    control_session('http://127.0.0.1:8000', 'replace', path)

    def test_demo_controller_does_not_guess_between_multiple_sessions(self):
        with tempfile.TemporaryDirectory() as root:
            for name in ('one', 'two'):
                path = Path(root) / ('btu-live-browser-private-' + name)
                path.mkdir()
                (path / 'preview-private.json').write_text('{}')
            with patch('manual_demo.tempfile.gettempdir', return_value=root):
                with patch('manual_demo.DemoClient.request', side_effect=AssertionError('No HTTP')):
                    with self.assertRaisesRegex(ValueError, 'One private fixture'):
                        control_session('http://127.0.0.1:8000', 'replace')

    def test_unique_owned_names(self):
        names = {test_database_name('regression') for _ in range(100)}
        self.assertEqual(len(names), 100)
        self.assertTrue(all(n.startswith('test_owned_') and len(n) < 63 for n in names))

    def test_failure_and_interruption_remove_only_owned_artifacts(self):
        for failure in (RuntimeError, KeyboardInterrupt):
            with tempfile.TemporaryDirectory() as unrelated:
                demo = Path(unrelated) / 'preserve-demo'
                demo.write_text('existing')
                with self.assertRaises(failure):
                    with DisposableRun() as run:
                        owned = Path(run.enter_context(tempfile.TemporaryDirectory()))
                        for name in ('document.pdf', 'upload.xlsx', 'message.otp', 'session'):
                            (owned / name).write_text('synthetic')
                        raise failure()
                self.assertFalse(owned.exists())
                self.assertEqual(demo.read_text(), 'existing')

    def test_cleanup_failure_does_not_skip_other_cleanup(self):
        seen = []
        with self.assertRaises(RuntimeError):
            with DisposableRun() as run:
                run.callback(seen.append, 'database disposed')
                run.callback(lambda: (_ for _ in ()).throw(RuntimeError()))
                run.callback(seen.append, 'server stopped')
        self.assertEqual(seen, ['server stopped', 'database disposed'])

    def test_interrupted_child_is_killed_and_reaped(self):
        with patch('config.disposable_tests.subprocess.Popen') as start, patch('config.disposable_tests.subprocess.run'), patch('config.disposable_tests.os.killpg', create=True):
            child = start.return_value
            child.communicate.side_effect = KeyboardInterrupt()
            child.poll.return_value = None
            with DisposableRun() as run, self.assertRaises(KeyboardInterrupt):
                run.command(['synthetic-child'])
            child.kill.assert_called_once()
            self.assertEqual(child.wait.call_count, 1)

    def test_fixture_cleanup_failure_is_reported(self):
        from unittest.mock import Mock
        fixture = Mock()
        fixture.doCleanups.return_value = False
        seen = []
        with self.assertRaisesRegex(RuntimeError, 'fixture cleanup'):
            with DisposableRun() as run:
                run.callback(seen.append, 'remaining cleanup')
                run.fixture(fixture)
        self.assertEqual(seen, ['remaining cleanup'])

    def test_real_child_timeout_is_reaped(self):
        real_start = subprocess.Popen
        children = []
        def start(*args, **kwargs):
            child = real_start(*args, **kwargs)
            children.append(child)
            return child
        with patch('config.disposable_tests.subprocess.Popen', side_effect=start):
            with DisposableRun() as run, self.assertRaises(subprocess.TimeoutExpired):
                run.command([sys.executable, '-c', 'import time; time.sleep(60)'], timeout=0.1)
        self.assertIsNotNone(children[0].poll())


if __name__ == '__main__':
    unittest.main()
