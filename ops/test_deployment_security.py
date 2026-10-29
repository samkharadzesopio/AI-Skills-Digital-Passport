"""Production middleware regression with synthetic settings, no DB or external IO.

Run directly with Python. Never reads backend/.env or uses deployment credentials.
Successful authentication is covered separately by the disposable PG HTTP suite.
"""
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
BACKEND = 'ai-skills-digital-passport.onrender.com'
FRONTEND = 'https://ai-skills-digital-passport-a3ux.vercel.app'
os.environ.update(
    DJANGO_SETTINGS_MODULE='config.settings', DJANGO_DEBUG='false',
    DJANGO_SECRET_KEY=secrets.token_urlsafe(64),
    AUTH_TOKEN_PEPPER=secrets.token_urlsafe(48),
    ACCOUNTS_OTP_HMAC_KEY=secrets.token_urlsafe(48),
    ACCOUNTS_ACTIVE_STUDENT_STATUSES='SYNTHETIC_TEST_ONLY',
    DATABASE_URL='postgresql://synthetic:synthetic@127.0.0.1:1/synthetic?sslmode=require',
    DJANGO_ALLOWED_HOSTS=BACKEND, DJANGO_CSRF_TRUSTED_ORIGINS=FRONTEND,
    DJANGO_TRUST_X_FORWARDED_PROTO='true',
    DJANGO_EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
    DJANGO_EMAIL_HOST='smtp.synthetic.invalid', DJANGO_EMAIL_USE_TLS='true',
    DJANGO_EMAIL_USE_SSL='false', PASSPORT_BLOCKCHAIN_ENABLED='false',
    BTU_SPREADSHEET_GOOGLE_SOURCES_JSON='{}', BTU_CLASSROOM_ISSUER_REFERENCE='BTU-UNIVERSITY',
)

import django
with patch('dotenv.load_dotenv'):
    django.setup()
from django.conf import settings
from django.http import JsonResponse
from django.test import Client, SimpleTestCase, override_settings
from django.urls import path


def probe(request):
    return JsonResponse({'method': request.method, 'query': request.META['QUERY_STRING'],
                         'body_hash': hashlib.sha256(request.body).hexdigest()})


from config.urls import urlpatterns as application_urls
urlpatterns = [*application_urls, path('api/deployment-test/', probe)]


@override_settings(ROOT_URLCONF=__name__)
class DeploymentSecurityTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True, HTTP_HOST=BACKEND,
                             HTTP_X_FORWARDED_PROTO='https')

    def csrf(self):
        response = self.client.get('/api/accounts/csrf/')
        self.assertEqual(response.status_code, 200)
        self.assertRegex(response.json()['csrfToken'], r'^[A-Za-z0-9]{64}$')
        return response

    def test_old_host_allowlist_reproduces_400(self):
        with override_settings(ALLOWED_HOSTS=['btudigitalpassport.onrender.com']):
            with self.assertLogs('django.security.DisallowedHost', level='ERROR') as logs:
                response = self.client.get('/api/accounts/csrf/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid HTTP_HOST header', ''.join(logs.output))

    def test_secure_host_only_cookies_and_https(self):
        response = self.csrf()
        cookie = response.cookies['csrftoken']
        self.assertTrue(cookie['secure'])
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')
        self.assertEqual(cookie['domain'], '')
        self.assertEqual(cookie['path'], '/')
        self.assertTrue(settings.SESSION_COOKIE_SECURE)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')
        self.assertIsNone(settings.SESSION_COOKIE_DOMAIN)
        self.assertEqual(settings.SESSION_ENGINE, 'django.contrib.sessions.backends.db')
        self.assertFalse(settings.USE_X_FORWARDED_HOST)
        self.assertNotIn('Location', response)

    def test_untrusted_host_is_rejected(self):
        with self.assertLogs('django.security.DisallowedHost', level='ERROR'):
            response = self.client.get('/api/accounts/csrf/', HTTP_HOST='untrusted.invalid')
        self.assertEqual(response.status_code, 400)

    def test_missing_token_and_untrusted_origin_stay_forbidden(self):
        for endpoint in ('login/', 'otp/request/', 'otp/verify/'):
            with self.subTest(endpoint=endpoint), self.assertLogs('django.security.csrf', level='WARNING'):
                response = self.client.post('/api/accounts/' + endpoint, {}, content_type='application/json',
                                            HTTP_ORIGIN=FRONTEND)
                self.assertEqual(response.status_code, 403)
        token = self.csrf().json()['csrfToken']
        with self.assertLogs('django.security.csrf', level='WARNING'):
            response = self.client.post('/api/deployment-test/', {}, content_type='application/json',
                                        HTTP_ORIGIN='https://untrusted.invalid', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 403)

    def test_trusted_origin_retains_method_body_and_query(self):
        token = self.csrf().json()['csrfToken']
        body = json.dumps({'text': 'Synthetic ქართული', 'values': [1, 2]}).encode()
        query = 'kind=passport&reference=a%2Fb&tag=one&tag=two'
        response = self.client.post('/api/deployment-test/?' + query, body,
                                    content_type='application/json', HTTP_ORIGIN=FRONTEND,
                                    HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'method': 'POST', 'query': query,
                                          'body_hash': hashlib.sha256(body).hexdigest()})

    def test_proxy_https_misconfiguration_redirects_and_http_stays_https(self):
        with override_settings(SECURE_PROXY_SSL_HEADER=None):
            response = self.client.get('/api/accounts/csrf/')
            self.assertEqual(response.status_code, 301)
        response = self.client.get('/api/accounts/csrf/?next=a%2Fb', HTTP_X_FORWARDED_PROTO='http')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], f'https://{BACKEND}/api/accounts/csrf/?next=a%2Fb')

    def test_anonymous_private_access_is_denied(self):
        response = self.client.get('/api/accounts/me/')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response['Cache-Control'], 'no-store')


if __name__ == '__main__':
    unittest.main(verbosity=2)
