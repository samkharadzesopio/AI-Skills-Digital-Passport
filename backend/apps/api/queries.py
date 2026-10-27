"""Shared, bounded query plans for every private interface."""
from django.db.models import Count, Prefetch, Q
from apps.skills.models import Skill, VerifiedAchievement
from apps.credentials.models import Credential
from apps.passports.models import DigitalPassport, PassportVersion


def achievements():
    return VerifiedAchievement.objects.filter(verification_status='VERIFIED').select_related('skill', 'source_event').order_by('-earned_on', 'pk')


def recognized_skills(student_id=None):
    awards = achievements()
    if student_id is not None:
        awards = awards.filter(student_id=student_id)
    return Skill.objects.filter(verified_achievements__in=awards).distinct().order_by('skill_code', 'pk').prefetch_related(Prefetch('verified_achievements', queryset=awards[:100], to_attr='student_achievements'))


def credentials():
    # Historical credential associations are preserved regardless of later award state.
    awards = VerifiedAchievement.objects.select_related('skill', 'source_event').order_by('pk')
    return Credential.objects.prefetch_related(Prefetch('achievements', queryset=awards)).order_by('-issued_at', 'pk')


def versions():
    return PassportVersion.objects.filter(status='ISSUED', passport__status='ACTIVE').select_related('passport').prefetch_related('skill_snapshots', 'credential_snapshots').order_by('-version_number', 'pk')


def passports(include_inactive=False):
    rows=DigitalPassport.objects.select_related('latest_version').prefetch_related('latest_version__skill_snapshots', 'latest_version__credential_snapshots').order_by('pk')
    return rows if include_inactive else rows.filter(status='ACTIVE')


def validity_filters(now):
    issued = Q(status='ISSUED', issued_at__lte=now)
    return {
        'VALID': issued & (Q(expires_at__isnull=True) | Q(expires_at__gt=now)),
        'EXPIRED': issued & Q(expires_at__lte=now),
        'REVOKED': Q(status='REVOKED'),
        'INVALID': Q(status='ISSUED', issued_at__gt=now),
    }


def credential_counts(queryset, now):
    return queryset.aggregate(total=Count('pk'), **{key.lower(): Count('pk', filter=value) for key, value in validity_filters(now).items()})


def skill_distribution(queryset, field):
    return list(queryset.order_by().values(field).annotate(count=Count('pk', distinct=True)).order_by(field))
