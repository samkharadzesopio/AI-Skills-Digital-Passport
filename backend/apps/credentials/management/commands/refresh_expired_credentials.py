from django.core.management.base import BaseCommand, CommandError

from apps.credentials.passport_refresh import (
    DEFAULT_BATCH_SIZE,
    MAX_BATCH_SIZE,
    enqueue_expired_passport_refreshes,
    process_pending_passport_refreshes,
)


class Command(BaseCommand):
    help = "Queue and process a bounded batch of Passport refreshes for expired credentials."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        if not 1 <= batch_size <= MAX_BATCH_SIZE:
            raise CommandError(f"--batch-size must be between 1 and {MAX_BATCH_SIZE}.")
        enqueued = enqueue_expired_passport_refreshes(limit=batch_size)
        result = process_pending_passport_refreshes(batch_size=batch_size)
        self.stdout.write(
            self.style.SUCCESS(
                f"Expired credentials queued={enqueued}; "
                f"refreshes completed={result['completed']} retried={result['retried']} "
                f"failed={result['failed']} lease_lost={result['lease_lost']}"
            )
        )
