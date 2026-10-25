from django.core.management.base import BaseCommand
from apps.accounts.mail_queue import deliver_one


class Command(BaseCommand):
    help = 'Process up to 100 queued login/recovery mail jobs; no secrets are printed.'
    def handle(self, *args, **options):
        count = 0
        for _ in range(100):
            if not deliver_one():
                break
            count += 1
        self.stdout.write(f'Processed {count} delivery jobs.')
