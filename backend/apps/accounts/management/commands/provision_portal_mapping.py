import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from apps.accounts.models import User
from apps.accounts.portal import approve_mapping


class Command(BaseCommand):
    help = 'Load an explicitly approved institutional Google-sub / student-ID mapping. Never matches email.'

    def add_arguments(self, parser):
        parser.add_argument('--file', required=True)
        parser.add_argument('--actor-id', required=True)
        parser.add_argument('--approval-reference', required=True)

    def handle(self, *args, **options):
        try:
            path = Path(options['file'])
            if path.stat().st_size > 1024 * 1024:
                raise ValueError('Mapping input too large')
            rows = json.loads(path.read_text(encoding='utf-8-sig'))
            if not isinstance(rows, list) or not 1 <= len(rows) <= 5000:
                raise ValueError('Bounded list required')
            actor = User.objects.get(pk=options['actor_id'])
            with transaction.atomic():
                for row in rows:
                    if not isinstance(row, dict) or set(row) != {'google_sub', 'external_student_id'}:
                        raise ValueError('Explicit subject and institutional student ID required')
                    approve_mapping(actor=actor, subject=row['google_sub'], external_student_id=row['external_student_id'],
                        approval_reference=options['approval_reference'])
            self.stdout.write(f'Approved {len(rows)} mapping records. No academic records or awards created.')
        except Exception:
            raise CommandError('Mapping rejected. Check actor permission, approved source and identity conflicts. No input values printed.') from None
