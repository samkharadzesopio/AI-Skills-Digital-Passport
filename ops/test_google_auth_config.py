import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from configure_google_auth import configure, replace_setting


class GoogleLocalConfigTests(unittest.TestCase):
    def test_only_named_setting_changes_and_existing_variables_comments_survive(self):
        source = '# private local config\r\nOTHER=preserve-this\r\nVITE_GOOGLE_CLIENT_ID=old\r\nTAIL=also-preserve\r\n'
        result = replace_setting(source, 'VITE_GOOGLE_CLIENT_ID', 'new')
        self.assertEqual(result, source.replace('VITE_GOOGLE_CLIENT_ID=old', 'VITE_GOOGLE_CLIENT_ID=new'))

    def test_append_does_not_replace_existing_settings(self):
        self.assertEqual(replace_setting('OTHER=keep', 'GOOGLE_OAUTH_CLIENT_ID', 'new'), 'OTHER=keep\nGOOGLE_OAUTH_CLIENT_ID=new\n')

    def test_duplicates_refused(self):
        with self.assertRaises(ValueError):
            replace_setting('GOOGLE_OAUTH_CLIENT_ID=a\nGOOGLE_OAUTH_CLIENT_ID=b\n', 'GOOGLE_OAUTH_CLIENT_ID', 'new')

    def test_both_existing_files_preserved_and_no_value_printed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'frontend').mkdir(); (root / 'backend').mkdir()
            (root / 'frontend/.env.local').write_text('FRONTEND_PRIVATE=preserve\n')
            (root / 'backend/.env').write_text('BACKEND_PRIVATE=preserve\n')
            client = root / 'id.txt'; client.write_text('synthetic.apps.googleusercontent.com')
            with patch('configure_google_auth.ROOT', root), patch('builtins.print') as output:
                configure(client)
            self.assertTrue((root / 'frontend/.env.local').read_text().startswith('FRONTEND_PRIVATE=preserve\n'))
            self.assertTrue((root / 'backend/.env').read_text().startswith('BACKEND_PRIVATE=preserve\n'))
            self.assertNotIn(client.read_text(), str(output.call_args))


if __name__ == '__main__':
    unittest.main()
