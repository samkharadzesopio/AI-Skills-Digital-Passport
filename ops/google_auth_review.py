"""Owned local Google auth review configuration; synthetic mode is tests only."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import override_settings
from dotenv import dotenv_values


def configure(owned, directory, root, *, synthetic):
    if synthetic:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        client_id = '123456789-synthetic.apps.googleusercontent.com'
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        path = directory / 'google-test-private.pem'
        path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        path.chmod(0o600)
        public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
        owned.enter_context(patch('apps.accounts.google_auth.certificate_request',
            return_value=SimpleNamespace(status=200, data=json.dumps({'synthetic-key': public}).encode())))
    else:
        # Read only the two public IDs. Do not load production DB/provider settings.
        backend = os.environ.get('GOOGLE_OAUTH_CLIENT_ID') or dotenv_values(root / 'backend/.env').get('GOOGLE_OAUTH_CLIENT_ID', '')
        frontend = os.environ.get('VITE_GOOGLE_CLIENT_ID') or dotenv_values(root / 'frontend/.env.local').get('VITE_GOOGLE_CLIENT_ID', '')
        if (backend or '').strip() != (frontend or '').strip():
            raise RuntimeError('GOOGLE_OAUTH_CLIENT_ID and VITE_GOOGLE_CLIENT_ID must match; no Google request made.')
        client_id = (backend or '').strip()
    owned.enter_context(override_settings(GOOGLE_OAUTH_CLIENT_ID=client_id))
    return client_id
