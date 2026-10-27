from django.core.management.base import BaseCommand, CommandError
from apps.passports.publication import process_publications
from apps.passports.models import PassportPublication


class Command(BaseCommand):
    help = 'Generate official PDFs from the durable Passport publication queue.'
    def add_arguments(self,parser):
        parser.add_argument('--batch-size',type=int,default=20)
        parser.add_argument('--retry-failed',action='store_true')
    def handle(self,*args,**options):
        if not 1 <= options['batch_size'] <= 100:
            raise CommandError('Batch size must be between 1 and 100.')
        if options['retry_failed']:
            PassportPublication.objects.filter(state='FAILED').update(state='PENDING',attempts=0,next_attempt_at=None,error_code='')
        self.stdout.write(str(process_publications(options['batch_size'])))
