"""Provision immutable source profiles through an explicit operator review, never HTTP."""
import re

from django.db import transaction

from apps.integrations.models import SpreadsheetProfile
from .mapping import digest, validate_definition
from .validators import ImportValidationError


def profile_hash(profile):
    return digest({'key': profile.key, 'version': profile.version, 'source': profile.source,
                   'kind': profile.kind, 'definition': profile.definition,
                   'approval_reference': profile.approval_reference})


@transaction.atomic
def provision_profile(data):
    if not isinstance(data, dict) or set(data) != {'key', 'version', 'source', 'kind', 'definition', 'approval_reference'}:
        raise ImportValidationError('Supply exactly the documented profile manifest fields.')
    if not isinstance(data['key'], str) or not re.fullmatch(r'[a-z0-9_-]{1,80}', data['key']) or type(data['version']) is not int or data['version'] < 1:
        raise ImportValidationError('Invalid profile key or version.')
    if data['source'] not in ('BTU_EXCEL', 'BTU_GOOGLE_SHEETS') or not isinstance(data['approval_reference'], str) or not 1 <= len(data['approval_reference'].strip()) <= 255:
        raise ImportValidationError('An authorized source and institutional policy approval reference are required.')
    validate_definition(data['kind'], data['definition'])
    if data['source'] == 'BTU_GOOGLE_SHEETS' and not data['definition'].get('google_source'):
        raise ImportValidationError('Google profiles need a server-configured source key.')
    candidate = SpreadsheetProfile(**data)
    hashed = profile_hash(candidate)
    existing = SpreadsheetProfile.objects.filter(key=data['key'], version=data['version']).first()
    if existing:
        if existing.definition_sha256 != hashed:
            raise ImportValidationError('Profile versions are immutable. Provision a new version.')
        return existing
    candidate.definition_sha256 = hashed
    candidate.full_clean()
    candidate.save()
    return candidate
