"""Dedicated integration worker; never reads arbitrary sources or sends mail."""
import json
import time
from django.core.management.base import BaseCommand, CommandError
from apps.integrations.spreadsheet_automation import poll_due_sources


class Command(BaseCommand):
    help = 'Poll explicitly enabled approved Google awarded-skill profiles. Default: one bounded cycle.'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group()
        group.add_argument('--once', action='store_true')
        group.add_argument('--watch', action='store_true')
        parser.add_argument('--limit', type=int, default=10)

    def handle(self, *args, **options):
        if not 1 <= options['limit'] <= 100:
            raise CommandError('Use a source limit between 1 and 100.')
        while True:
            try:
                self.stdout.write(json.dumps(poll_due_sources(limit=options['limit']), sort_keys=True))
            except Exception:
                if not options['watch']:
                    raise CommandError('Automatic source poll failed; inspect sanitized source history.') from None
                self.stderr.write('Automatic source poll failed; retrying in the next bounded cycle.')
            if not options['watch']:
                return
            time.sleep(5)
