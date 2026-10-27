"""Controlled operator recovery; never signs or replaces a transaction."""
from django.core.management.base import BaseCommand, CommandError
from apps.blockchain.chain import ProofError
from apps.blockchain.services import recover_signed_operation


class Command(BaseCommand):
    help = 'Rebroadcast an inspected original transaction; never changes fees or nonces.'

    def add_arguments(self, parser):
        parser.add_argument('operation_id')
        parser.add_argument('--expected-transaction-hash', required=True)
        parser.add_argument('--rebroadcast', action='store_true')

    def handle(self, *args, **options):
        if not options['rebroadcast']:
            raise CommandError('Inspect the operation first; explicit --rebroadcast is required.')
        try:
            state = recover_signed_operation(
                options['operation_id'], expected_transaction_hash=options['expected_transaction_hash'],
            )
        except ProofError as error:
            raise CommandError('Recovery stopped: ' + error.code) from None
        except Exception:
            raise CommandError('Recovery unavailable; inspect the saved transaction before retrying.') from None
        self.stdout.write('Recovery assessment: ' + state)
