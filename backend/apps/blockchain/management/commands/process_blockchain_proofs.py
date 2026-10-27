import time

from django.core.management.base import BaseCommand, CommandError
from apps.blockchain.services import process_batch, reconcile_confirmed, retry_failed


class Command(BaseCommand):
    help = 'Process bounded PDF proof batches; --watch runs a separate signing worker.'

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=20)
        parser.add_argument('--watch', action='store_true')
        parser.add_argument('--retry-failed',action='store_true')

    def handle(self, *args, **options):
        if not 1 <= options['batch_size'] <= 100:
            raise CommandError('Batch size must be between 1 and 100.')
        if options['retry_failed']:
            self.stdout.write(f'Requeued transient failures: {retry_failed()}')
        while True:
            try:
                result = process_batch(batch_size=options['batch_size'])
                result['reconciled']=reconcile_confirmed(options['batch_size'])
                self.stdout.write(str(result))
            except Exception:
                if not options['watch']:
                    raise CommandError('Proof worker unavailable; check deployment policy and database.') from None
                self.stderr.write('Proof worker unavailable; retrying without exposing provider errors.')
            if not options['watch']:
                return
            time.sleep(15)
