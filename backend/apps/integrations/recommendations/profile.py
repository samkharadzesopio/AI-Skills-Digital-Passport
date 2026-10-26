from django.conf import settings
from django.db.models import F, Q
from django.utils import timezone
from apps.students.models import Student
from apps.skills.models import VerifiedAchievement
from .contracts import LearningProfile, RecommendationDataError

MAX_PROFILE_RECORDS = 2000


class LearningProfileRepository:
    def load(self, student_id, provider, catalog):
        student = Student.objects.only('external_student_id').get(pk=student_id)
        history = provider.get_completed_courses(student.external_student_id)
        if not isinstance(history, tuple) or len(history) > MAX_PROFILE_RECORDS or any(not isinstance(c, str) or len(c) > 100 for c in history):
            raise RecommendationDataError('Invalid academic history.')
        achievements = list(VerifiedAchievement.objects.filter(student_id=student_id, verification_status='VERIFIED')
                            .values('skill__skill_code', 'source_event__course_id', 'source_event__source')
                            .distinct()[:MAX_PROFILE_RECORDS + 1])
        if len(achievements) > MAX_PROFILE_RECORDS:
            raise RecommendationDataError('Academic profile exceeds the guidance limit.')
        completed = set(history)
        for row in achievements:
            if row['source_event__source'] in ('BTU_CLASSROOM', 'BTU_EXCEL', 'BTU_GOOGLE_SHEETS') and row['source_event__course_id']:
                completed.add(row['source_event__course_id'])
        by_id = {c.course_id: c for c in catalog}
        known = frozenset(completed & by_id.keys())
        inferred = frozenset(s for cid in known for s in by_id[cid].skills)
        verified = frozenset(row['skill__skill_code'] for row in achievements)
        approved = getattr(settings, 'VERIFICATION_TRUSTED_ISSUER_REFERENCES', ())
        passport = frozenset()
        if isinstance(approved, (list, tuple)) and approved:
            now = timezone.now()
            prefix = 'credential_links__credential__'
            filters = {
                'student_id': student_id, 'verification_status': 'VERIFIED',
                prefix+'status': 'ISSUED', prefix+'issued_at__lte': now,
                prefix+'issuer__is_trusted': True, prefix+'issuer__reference__in': approved,
                prefix+'issuer_reference': F(prefix+'issuer__reference'),
                prefix+'passport_snapshots__version__status': 'ISSUED',
                prefix+'passport_snapshots__version__latest_for_passports__student_id': student_id,
            }
            rows = list(VerifiedAchievement.objects.filter(**filters).filter(
                Q(**{prefix+'expires_at__isnull': True}) | Q(**{prefix+'expires_at__gt': now})
            ).values_list('skill__skill_code', flat=True).distinct()[:MAX_PROFILE_RECORDS + 1])
            if len(rows) > MAX_PROFILE_RECORDS:
                raise RecommendationDataError('Passport guidance profile exceeds the limit.')
            passport = frozenset(rows)
        warnings = []
        if not known:
            warnings.append('NO_MAPPED_COMPLETED_COURSES')
        if completed - by_id.keys():
            warnings.append('UNMAPPED_COMPLETED_COURSES')
        return LearningProfile(known, verified, passport, inferred, tuple(warnings))
