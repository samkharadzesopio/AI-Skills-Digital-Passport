import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from apps.integrations.importers.profiles import provision_profile


class Command(BaseCommand):
    help = 'Install an institution-reviewed immutable source profile (disabled by default). Never approves individual rows.'

    def add_arguments(self, parser):
        parser.add_argument('--manifest', required=True)
        parser.add_argument('--enable', action='store_true', help='Explicitly authorize this reviewed profile; channel approval is still required.')

    def handle(self, *args, **options):
        try:
            path = Path(options['manifest'])
            if path.stat().st_size > 100_000:
                raise ValueError()
            profile = provision_profile(json.loads(path.read_text(encoding='utf-8')))
            if options['enable']:
                profile.enabled = True
                profile.save(update_fields=['enabled'])
        except Exception:
            raise CommandError('Profile provisioning failed. Check the reviewed manifest and database; no source values are displayed.') from None
        self.stdout.write(f'Profile {profile.pk}: {profile.key} v{profile.version}; enabled={profile.enabled}')
