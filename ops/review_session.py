"""Synthetic source for an explicitly selected, owned local review session.

Only the Google provider boundary is replaced. Session/CSRF, institutional
profile authorization, mapping, durable polling, issuance and Anvil are real.
"""
import json
from unittest.mock import patch

from django.test import override_settings
from apps.integrations.importers.mapping import digest
from apps.integrations.importers.profiles import provision_profile
from apps.integrations.test_spreadsheet_mapping import definition, grid
from apps.skills.models import Skill


def prepare_synthetic_source(owned, fixture, directory):
    # The generic PDF fixture uses "Active"; this approved synthetic source
    # deliberately accepts the exact institutional status "ACTIVE" only.
    fixture.student.student_status = 'ACTIVE'
    fixture.student.save(update_fields=['student_status'])
    target = {'spreadsheet_id': 'SYNTHETIC_REVIEW_NO_GOOGLE',
              'worksheet': 'Passport Skill Records', 'range': 'A1:F20'}
    owned.enter_context(override_settings(
        BTU_CLASSROOM_ISSUER_REFERENCE='BTU-UNIVERSITY',
        BTU_AUTHORIZED_COMPLETION_SOURCES=['BTU_GOOGLE_SHEETS', 'BTU_EXCEL'],
        BTU_SPREADSHEET_GOOGLE_SOURCES={'synthetic_review': target},
        BTU_GOOGLE_SHEET_ID='', GOOGLE_SERVICE_ACCOUNT_FILE=''))
    skill = Skill.objects.create(skill_code='SYNTHETIC-REVIEW-AWARD',
        skill_name='Synthetic Integrated AI Evidence', category='AI',
        description='Local synthetic acceptance evidence only.',
        stamp_type='FOCUSED', badge_asset_id='synthetic')
    data = {**definition(), 'google_source': 'synthetic_review', 'allowed_skill_codes': [skill.skill_code]}
    profile = provision_profile({'key': 'synthetic-review-awards', 'version': 1,
        'source': 'BTU_GOOGLE_SHEETS', 'kind': 'SKILL_AWARD', 'definition': data,
        'approval_reference': 'SYNTHETIC-LOCAL-REVIEW-POLICY'})
    profile.enabled = True
    profile.save(update_fields=['enabled'])
    source = directory / 'synthetic-source.json'
    row = [fixture.student.external_student_id, 'SYNTHETIC-TEAM-RECORD',
           skill.skill_code, '2026-10-18', 'CONFIRMED']
    source.write_text(json.dumps(grid(row)), encoding='utf-8')

    def read(requested):
        if requested.pk != profile.pk:
            raise ValueError('Only the owned synthetic profile is available.')
        rows = json.loads(source.read_text(encoding='utf-8'))
        return rows, digest({'target': target, 'rows': rows})

    for boundary in ('spreadsheet_automation', 'importers.preview', 'spreadsheet_views'):
        owned.enter_context(patch(f'apps.integrations.{boundary}.read_profile_sheet', side_effect=read))
    return {'profile_id': str(profile.pk), 'source_file': str(source), 'skill_name': skill.skill_name}
