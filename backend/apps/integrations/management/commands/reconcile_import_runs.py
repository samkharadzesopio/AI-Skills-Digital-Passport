from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from apps.integrations.models import ImportRun
from apps.integrations.importers.durable import reconcile_run


class Command(BaseCommand):
    help = 'Reconcile up to 100 incomplete import histories from durable event states.'
    def handle(self, *args, **options):
        for run in ImportRun.objects.filter(Q(state__in=['FAILED', 'PARTIAL']) | Q(state='RUNNING', created_at__lte=timezone.now() - timedelta(minutes=5))).order_by('created_at')[:100]:
            reconcile_run(run)
        self.stdout.write('Import histories reconciled.')
