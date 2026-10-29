"""Copy only a public Web Client ID into ignored local env files, never echo it."""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def replace_setting(contents, name, value):
    pattern = re.compile(r'^([ \t]*(?:export[ \t]+)?' + re.escape(name) + r'[ \t]*=)[^\r\n]*', re.MULTILINE)
    matches = list(pattern.finditer(contents))
    if len(matches) > 1:
        raise ValueError('Duplicate Client ID settings must be resolved locally first.')
    if matches:
        result = pattern.sub(lambda m: m[1] + value, contents)
    else:
        newline = '\r\n' if '\r\n' in contents else '\n'
        result = contents + (newline if contents and not contents.endswith(('\r', '\n')) else '') + name + '=' + value + newline
    # Prove that every pre-existing, unrelated line remains byte-for-byte intact.
    original_other = [line for line in contents.splitlines(keepends=True) if not pattern.match(line)]
    result_other = [line for line in result.splitlines(keepends=True) if not pattern.match(line)]
    if ''.join(original_other).rstrip('\r\n') != ''.join(result_other).rstrip('\r\n'):
        raise ValueError('Refusing to change unrelated environment settings.')
    return result


def configure(client_id_file):
    value = Path(client_id_file).read_text(encoding='utf-8-sig').strip()
    if len(value) > 255 or not re.fullmatch(r'[A-Za-z0-9_-]+\.apps\.googleusercontent\.com', value):
        raise ValueError('Input must contain only the OAuth Web Client ID, never a secret or credentials JSON.')
    changes = []
    for relative, name in (('frontend/.env.local', 'VITE_GOOGLE_CLIENT_ID'), ('backend/.env', 'GOOGLE_OAUTH_CLIENT_ID')):
        path = ROOT / relative
        contents = path.read_bytes().decode('utf-8') if path.exists() else ''
        changes.append((path, contents, replace_setting(contents, name, value)))
    for path, original, changed in changes:
        # Refuse concurrent edits instead of overwriting another developer's work.
        if (path.read_bytes().decode('utf-8') if path.exists() else '') != original:
            raise ValueError('Environment changed concurrently; retry after review.')
        path.write_bytes(changed.encode('utf-8'))
    print('Configured matching Google Client IDs; unrelated variables preserved. No secret or Client ID was printed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client-id-file', required=True)
    try:
        configure(parser.parse_args().client_id_file)
    except (OSError, ValueError):
        raise SystemExit('Configuration failed. Check the private input file, duplicate settings and concurrent edits. No values printed.') from None
