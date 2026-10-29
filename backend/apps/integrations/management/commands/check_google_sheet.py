"""Explicitly opted-in, read-only Google/profile check. Never imports or issues."""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.integrations.importers.mapping import map_grid
from apps.integrations.importers.preview import check_profile
from apps.integrations.importers.sheet_source import read_profile_sheet
from apps.integrations.models import SpreadsheetProfile


class Command(BaseCommand):
    help = 'Read an approved Google profile only with explicit external-access approval; no database writes.'

    def add_arguments(self, parser):
        parser.add_argument('--profile-id', required=True)
        parser.add_argument('--approval-reference', required=True)
        parser.add_argument('--allow-google-read', action='store_true')

    def handle(self, *args, **options):
        if not options['allow_google_read']:
            raise CommandError('No Google request made. Supply --allow-google-read only after explicit approval.')
        try:
            profile = SpreadsheetProfile.objects.get(pk=options['profile_id'], source='BTU_GOOGLE_SHEETS', enabled=True)
            if options['approval_reference'] != profile.approval_reference:
                raise ValueError()
            check_profile(profile)
            rows, hashed = read_profile_sheet(profile)
            mapped = map_grid(rows, kind=profile.kind, definition=profile.definition)
        except Exception:
            raise CommandError('Google/profile check failed. Check approved configuration, policy and private sharing; no data imported.') from None
        self.stdout.write(json.dumps({'google_read': 'PASS', 'source_sha256': hashed,
                                     'mapped_records': len(mapped['records']), 'issues': len(mapped['issues']),
                                     'imported': False}))
