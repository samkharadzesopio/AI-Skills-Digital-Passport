"""Linux-only production bootstrap acceptance; synthetic settings, no database IO.

Run in an isolated checkout/container with the pinned requirements installed.
Never loads a private .env, sends email, connects to Neon or starts a deployment.
"""
import http.client
import json
import os
from pathlib import Path
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import threading


def main():
    wsgi_only = '--wsgi-only' in sys.argv
    if os.name != 'posix' and not wsgi_only:
        raise SystemExit('Run this Gunicorn acceptance check on Linux.')
    root = Path(__file__).resolve().parents[1]
    if (root / 'backend/.env').exists():
        raise SystemExit('Refusing a checkout containing backend/.env.')
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(('DJANGO_', 'PG', 'PASSPORT_BLOCKCHAIN_', 'GUNICORN_'))}
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    env.update(
        DJANGO_SETTINGS_MODULE='config.settings', DJANGO_DEBUG='false',
        DJANGO_SECRET_KEY=secrets.token_urlsafe(64), AUTH_TOKEN_PEPPER=secrets.token_urlsafe(48),
        ACCOUNTS_OTP_HMAC_KEY=secrets.token_urlsafe(48),
        ACCOUNTS_ACTIVE_STUDENT_STATUSES='SYNTHETIC_ACTIVE',
        DATABASE_URL='postgresql://synthetic@127.0.0.1:1/synthetic?sslmode=require',
        DJANGO_ALLOWED_HOSTS='backend.production.invalid',
        DJANGO_CSRF_TRUSTED_ORIGINS='https://frontend.production.invalid',
        DJANGO_TRUST_X_FORWARDED_PROTO='true', DJANGO_EMAIL_HOST='smtp.invalid',
        DJANGO_EMAIL_USE_TLS='true', DJANGO_EMAIL_USE_SSL='false',
        PYTHONDONTWRITEBYTECODE='1', WEB_CONCURRENCY='1', PORT=str(port),
    )
    if wsgi_only:
        subprocess.run([sys.executable, 'backend/manage.py', 'collectstatic', '--noinput'],
                       cwd=root, env=env, check=True, stdout=subprocess.DEVNULL)
    else:
        subprocess.run(['bash', '-n', 'ops/render_build.sh', 'ops/render_start.sh'], cwd=root, check=True)
        subprocess.run(['bash', 'ops/render_build.sh'], cwd=root, env=env, check=True,
                       stdout=subprocess.DEVNULL)
    assert (root / 'backend/staticfiles/staticfiles.json').is_file()
    if not wsgi_only:
        subprocess.run(['gunicorn', '--config', '../ops/gunicorn.conf.py', '--check-config',
                        'config.wsgi:application'], cwd=root / 'backend', env=env, check=True)

    server = None
    thread = None
    if wsgi_only:
        os.environ.clear()
        os.environ.update(env)
        sys.path.insert(0, str(root / 'backend'))
        from config.wsgi import application
        from wsgiref.simple_server import WSGIRequestHandler, make_server

        class Quiet(WSGIRequestHandler):
            def log_message(self, *args):
                pass

        server = make_server('127.0.0.1', port, application, handler_class=Quiet)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

    def request(path, *, host='backend.production.invalid', method='GET', headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        try:
            conn.request(method, path, headers={
                'Host': host, 'X-Forwarded-Proto': 'https', 'Accept': 'application/json',
                **(headers or {}),
            })
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    with tempfile.TemporaryFile() as log:
        process = None if wsgi_only else subprocess.Popen(
            ['bash', 'ops/render_start.sh'], cwd=root, env=env, stdout=log, stderr=log)
        try:
            for _ in range(100):
                if process is not None and process.poll() is not None:
                    raise AssertionError('Gunicorn exited before readiness.')
                try:
                    status, headers, body = request('/api/accounts/csrf/')
                    break
                except (OSError, http.client.HTTPException):
                    time.sleep(0.1)
            else:
                raise AssertionError('Gunicorn readiness timed out.')
            assert status == 200
            assert re.fullmatch(r'[A-Za-z0-9]{64}', json.loads(body)['csrfToken'])
            cookie = headers['Set-Cookie']
            assert all(flag in cookie for flag in ('Secure', 'HttpOnly', 'SameSite=Lax'))
            assert 'Domain=' not in cookie
            assert request('/api/accounts/csrf/', host='untrusted.invalid')[0] == 400
            for path in ('/api/accounts/me/', '/api/student/dashboard/', '/api/admin/catalog/'):
                status, headers, body = request(path)
                assert status == 403, path
                assert headers['Content-Type'].startswith('application/json'), path
            assert request('/api/accounts/google/challenge/', method='POST', headers={
                'Origin': 'https://frontend.production.invalid'})[0] == 403
            status, headers, body = request('/static/rest_framework/css/bootstrap.min.css')
            assert status == 200 and 'text/css' in headers['Content-Type'] and body
            assert request('/media/unissued.pdf')[0] == 404
            print(('PASS production WSGI (Gunicorn not exercised): ' if wsgi_only else
                   'PASS Linux Gunicorn: ') + 'real config.wsgi import and production startup; '
                  'CSRF JSON/secure host-only cookie, wrong-host 400, anonymous private API '
                  'denials, missing-CSRF denial, collected static CSS and media isolation. '
                  'Synthetic configuration; no database, email, Google or live services used.')
        finally:
            if server is not None:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
            if process is not None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == '__main__':
    main()
