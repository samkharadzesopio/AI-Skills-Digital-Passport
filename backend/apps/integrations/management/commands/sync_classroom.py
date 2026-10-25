from django.core.management.base import BaseCommand
from apps.integrations.classroom_automation import ClassroomCredentialAutomation


class Command(BaseCommand):
    help = 'Read the trusted simulated Classroom adapter; default is a write-free preview.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Persist events, achievements and credentials.')

    def handle(self, *args, **options):
        self.stdout.write(str(ClassroomCredentialAutomation().synchronize(dry_run=not options['apply'])))
