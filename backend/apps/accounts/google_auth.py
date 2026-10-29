"""Verified Workspace authentication; academic ownership is never inferred from email."""
import hmac
import json
import logging
import re
import secrets
import threading
import time
from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID

import requests
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from google.auth.exceptions import GoogleAuthError
from google.oauth2 import id_token
from rest_framework.exceptions import PermissionDenied

from .identity import authorized_student_id
from .models import GoogleIdentity, GoogleLoginChallenge, User
from .otp_store import _consume_budgets
from .otp_utils import normalize_btu_email, normalize_client_ip, security_digest

CERTIFICATES_URL = 'https://www.googleapis.com/oauth2/v1/certs'
CHALLENGE_SECONDS = 300
logger = logging.getLogger(__name__)


class GoogleProblem(Exception):
    def __init__(self, code, status=400):
        self.code, self.status = code, status


class GoogleCertificates:
    """Only Google's fixed public certificate endpoint; bounded IO and caching."""
    def __init__(self):
        self.lock = threading.Lock()
        self.cached = None
        self.until = 0

    def __call__(self, url, method='GET', **kwargs):
        if url != CERTIFICATES_URL or method != 'GET':
            raise GoogleProblem('GOOGLE_UNAVAILABLE', 503)
        with self.lock:
            if self.cached is not None and time.monotonic() < self.until:
                return self.cached
            try:
                with requests.Session() as client:
                    client.trust_env = False
                    with client.get(url, timeout=(3, 5), allow_redirects=False, stream=True) as response:
                        response.raise_for_status()
                        data = bytearray()
                        for chunk in response.iter_content(8192):
                            data.extend(chunk)
                            if len(data) > 128 * 1024:
                                raise ValueError('Certificate response too large')
                        body = bytes(data)
                        if response.status_code != 200 or not isinstance(json.loads(body), dict):
                            raise ValueError('Invalid certificate response')
                        match = re.search(r'(?:^|,)\s*max-age=(\d+)', response.headers.get('Cache-Control', ''))
                        age = int(response.headers.get('Age', '0'))
                        seconds = max(0, min(3600, int(match[1]) - age)) if match else 0
                        self.cached = SimpleNamespace(status=200, data=body, headers=dict(response.headers))
                        self.until = time.monotonic() + seconds
                        return self.cached
            except (requests.RequestException, ValueError, TypeError):
                raise GoogleProblem('GOOGLE_UNAVAILABLE', 503) from None


certificate_request = GoogleCertificates()


def client_id():
    value = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '')
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]+\.apps\.googleusercontent\.com', value) or len(value) > 255:
        raise GoogleProblem('GOOGLE_NOT_CONFIGURED', 503)
    return value


def rate_limit(request, scope):
    address = normalize_client_ip(request.META.get('REMOTE_ADDR'))
    with transaction.atomic():
        _consume_budgets(scope='google-' + scope,
            email_digest=security_digest('google.session', request.session.session_key or 'anonymous:' + address),
            ip_digest=security_digest('accounts.ip', address),
            email_limit=10, ip_limit=30, now=timezone.now())


def linked_student(request, *, fresh_otp=False):
    user = request.user
    if not user or not user.is_authenticated or user.role != User.Role.STUDENT:
        raise GoogleProblem('GOOGLE_STUDENT_REQUIRED', 403)
    try:
        authorized_student_id(user)
    except PermissionDenied:
        raise GoogleProblem('GOOGLE_STUDENT_REQUIRED', 403) from None
    if fresh_otp:
        proof = request.session.get('google_link_otp', {})
        at = proof.get('at') if isinstance(proof, dict) else None
        age = timezone.now().timestamp() - at if type(at) in (float, int) else -1
        if not isinstance(proof, dict) or proof.get('user_id') != str(user.pk) or not 0 <= age < CHALLENGE_SECONDS:
            raise GoogleProblem('GOOGLE_FRESH_OTP_REQUIRED', 403)
    return user


def begin(request, intent):
    audience = client_id()
    if not request.session.session_key:
        request.session.create()
    rate_limit(request, 'challenge')
    if intent == 'link':
        user = linked_student(request, fresh_otp=True)
    elif intent == 'login':
        if request.user and request.user.is_authenticated:
            raise GoogleProblem('GOOGLE_SIGN_OUT_REQUIRED', 403)
        user = None
    else:
        raise GoogleProblem('GOOGLE_INVALID_REQUEST')
    nonce = secrets.token_urlsafe(32)
    challenge = GoogleLoginChallenge.objects.create(
        nonce_digest=security_digest('google.nonce', nonce),
        session_digest=security_digest('google.session', request.session.session_key),
        intent=intent, user=user, audience=audience,
        expires_at=timezone.now() + timedelta(seconds=CHALLENGE_SECONDS))
    return {'challenge_id': str(challenge.pk), 'nonce': nonce, 'expires_in': CHALLENGE_SECONDS}


def _reject_token(reason):
    # Only fixed categories reach the logger; never credentials, claims or exceptions.
    logger.warning('google_id_token_rejected reason=%s', reason)
    raise GoogleProblem('GOOGLE_INVALID_TOKEN') from None


def _verification_failure_reason(error):
    # The pinned verifier embeds claims/tokens in errors. Classify, never log them.
    message = str(error)
    for prefix, category in (
        ('Could not verify token signature.', 'signature_invalid'),
        ('Token has wrong audience', 'audience_mismatch'),
        ('Wrong issuer', 'issuer_mismatch'),
        ('Token expired', 'token_expired'),
        ('Token used too early', 'token_used_too_early'),
        ('Token does not contain required claim', 'required_claim_missing'),
        ('Certificate for key id ', 'signing_key_unavailable'),
        ('Unsupported signature algorithm ', 'signature_algorithm_invalid'),
        ('Wrong number of segments in token', 'credential_malformed'),
    ):
        if message.startswith(prefix):
            return category
    return 'token_verification_failed'


def verify_credential(credential, audience, nonce_digest):
    if not isinstance(credential, str) or not 1 <= len(credential) <= 16384:
        _reject_token('credential_format_invalid')
    try:
        claims = id_token.verify_oauth2_token(credential, certificate_request, audience=audience)
    except (ValueError, TypeError, KeyError, GoogleAuthError) as error:
        _reject_token(_verification_failure_reason(error))
    try:
        # Exact checks supplement the maintained library's cryptographic validation.
        if claims.get('aud') != audience:
            _reject_token('audience_mismatch')
        if claims.get('azp', audience) != audience:
            _reject_token('authorized_party_mismatch')
        if claims.get('iss') not in ('accounts.google.com', 'https://accounts.google.com'):
            _reject_token('issuer_mismatch')
        if claims.get('email_verified') is not True:
            _reject_token('email_unverified')
        if claims.get('hd') != 'btu.edu.ge':
            _reject_token('hosted_domain_missing' if claims.get('hd') is None else 'hosted_domain_mismatch')
        if type(claims.get('exp')) is not int:
            _reject_token('token_expiry_invalid')
        if claims['exp'] <= time.time():
            _reject_token('token_expired')
        if not isinstance(claims.get('sub'), str) or not 1 <= len(claims['sub']) <= 255:
            _reject_token('subject_invalid')
        if not isinstance(claims.get('nonce'), str):
            _reject_token('nonce_missing')
        if not hmac.compare_digest(security_digest('google.nonce', claims['nonce']), nonce_digest):
            _reject_token('nonce_mismatch')
        try:
            email = normalize_btu_email(claims.get('email'))
        except ValueError:
            _reject_token('email_invalid')
        return claims['sub'], email
    except (ValueError, TypeError, KeyError, GoogleAuthError):
        _reject_token('claims_invalid')


def finish(request, challenge_id, credential):
    audience = client_id()
    rate_limit(request, 'credential')
    try:
        pk = UUID(str(challenge_id))
    except (ValueError, TypeError, AttributeError):
        raise GoogleProblem('GOOGLE_INVALID_CHALLENGE') from None
    # Consume before verification, in a committed transaction. Invalid tokens,
    # provider outages and racing submissions all require a fresh challenge.
    with transaction.atomic():
        challenge = GoogleLoginChallenge.objects.select_for_update().filter(pk=pk).first()
        if (not challenge or challenge.consumed_at or challenge.expires_at <= timezone.now()
                or challenge.audience != audience or not request.session.session_key
                or not hmac.compare_digest(challenge.session_digest,
                    security_digest('google.session', request.session.session_key))):
            raise GoogleProblem('GOOGLE_INVALID_CHALLENGE')
        challenge.consumed_at = timezone.now()
        challenge.save(update_fields=['consumed_at'])
    subject, email = verify_credential(credential, audience, challenge.nonce_digest)
    try:
        with transaction.atomic():
            if challenge.intent == 'link':
                current = linked_student(request, fresh_otp=True)
                if current.pk != challenge.user_id:
                    raise GoogleProblem('GOOGLE_STUDENT_REQUIRED', 403)
                user = User.objects.select_for_update(of=('self',)).select_related('student').get(pk=current.pk)
                if user.email != email:
                    raise GoogleProblem('GOOGLE_IDENTITY_CONFLICT', 409)
                existing = GoogleIdentity.objects.filter(user=user).first()
                if existing and existing.subject != subject:
                    raise GoogleProblem('GOOGLE_IDENTITY_CONFLICT', 409)
                if not existing:
                    GoogleIdentity.objects.create(user=user, subject=subject)
                request.session.pop('google_link_otp', None)
            else:
                if request.user and request.user.is_authenticated:
                    raise GoogleProblem('GOOGLE_SIGN_OUT_REQUIRED', 403)
                identity = GoogleIdentity.objects.filter(subject=subject).first()
                if identity is None:
                    # A new subject gets an independent principal even if the
                    # email matches a historical Student or administrator.
                    user = User(email=email, portal_only=True, role=User.Role.STUDENT, is_email_verified=True)
                    user.set_unusable_password()
                    user.save()
                    identity = GoogleIdentity.objects.create(user=user, subject=subject)
                user = User.objects.select_for_update(of=('self',)).select_related('student').get(pk=identity.user_id)
            if user.role != User.Role.STUDENT or (challenge.intent == 'link' and user.email != email):
                raise GoogleProblem('GOOGLE_STUDENT_REQUIRED', 403)
            try:
                from .portal import workspace_user
                workspace_user(user)
            except PermissionDenied:
                raise GoogleProblem('GOOGLE_STUDENT_REQUIRED', 403) from None
            user._workspace_authoritative = True
            return user, challenge.intent
    except IntegrityError:
        raise GoogleProblem('GOOGLE_IDENTITY_CONFLICT', 409) from None
