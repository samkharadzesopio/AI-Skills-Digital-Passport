from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone
from apps.integrations.classroom_automation import process_event, require_postgres
from apps.integrations.models import ClassroomSyncEvent as Event


class Command(BaseCommand):
    help = 'Resume up to 100 received/incomplete or due retryable Classroom events.'

    def handle(self, *args, **options):
        require_postgres()
        rows = Event.objects.filter(attempts__lt=5).filter(
            Q(state__in=[Event.State.RECEIVED, Event.State.ACHIEVEMENTS_RECORDED])
            | Q(state=Event.State.FAILED, retryable=True, next_retry_at__lte=timezone.now())
        ).order_by('created_at').values_list('pk', flat=True)[:100]
        counts = {'issued': 0, 'skipped': 0, 'failed': 0}
        for event_id in list(rows):
            counts[process_event(event_id)] += 1
        self.stdout.write(str(counts))
