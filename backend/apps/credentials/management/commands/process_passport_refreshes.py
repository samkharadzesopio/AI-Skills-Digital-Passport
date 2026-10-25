from django.core.management.base import BaseCommand, CommandError

from apps.credentials.passport_refresh import (
    DEFAULT_BATCH_SIZE,
    MAX_BATCH_SIZE,
    process_pending_passport_refreshes,
    retry_failed_passport_refreshes,
)


class Command(BaseCommand):
    help = "Process a bounded batch of durable Credential-to-Passport refresh requests."

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
        parser.add_argument(
            "--retry-failed",
            action="store_true",
            help="Requeue up to --batch-size terminal failures before processing.",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        if not 1 <= batch_size <= MAX_BATCH_SIZE:
            raise CommandError(f"--batch-size must be between 1 and {MAX_BATCH_SIZE}.")
        requeued = (
            retry_failed_passport_refreshes(limit=batch_size)
            if options["retry_failed"]
            else 0
        )
        result = process_pending_passport_refreshes(batch_size=batch_size)
        self.stdout.write(
            self.style.SUCCESS(
                "Passport refresh batch: "
                f"claimed={result['claimed']} completed={result['completed']} "
                f"retried={result['retried']} failed={result['failed']} "
                f"lease_lost={result['lease_lost']} requeued={requeued}"
            )
        )
