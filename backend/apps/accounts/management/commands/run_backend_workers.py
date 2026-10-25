"""Portable bounded worker cycle; no schema changes or automatic mock ingestion."""
import time
from django.core.management import call_command
from django.core.management.base import BaseCommand
from apps.accounts.mail_queue import deliver_one


class Command(BaseCommand):
    help = 'Drain queued auth mail and poll pending event/import recovery. Never ingests mock completions.'

    def add_arguments(self, parser):
        parser.add_argument('--once', action='store_true', help='Run one bounded cycle for operator smoke checks.')

    def handle(self, *args, **options):
        next_recovery = 0
        next_cleanup = 0
        while True:
            try:
                for _ in range(100):
                    if not deliver_one():
                        break
                now = time.monotonic()
                if now >= next_recovery:
                    call_command('retry_classroom_events', stdout=self.stdout)
                    call_command('reconcile_import_runs', stdout=self.stdout)
                    next_recovery = now + 60
                if now >= next_cleanup:
                    call_command('purge_expired_auth_state', stdout=self.stdout)
                    call_command('clearsessions', stdout=self.stdout)
                    next_cleanup = now + 3600
            except Exception as exc:
                # Never include exception strings: delivery failures can contain codes.
                if options['once']:
                    from django.core.management.base import CommandError
                    raise CommandError(f'Worker cycle failed ({type(exc).__name__}).') from None
                self.stderr.write(f'Worker cycle failed ({type(exc).__name__}); retrying.')
            if options['once']:
                break
            time.sleep(5)
