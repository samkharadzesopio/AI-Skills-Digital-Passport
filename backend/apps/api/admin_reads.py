"""Permissioned projections for the live Admin UI; no policy or identity writes."""
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response

from apps.credentials.models import Credential
from apps.integrations.repositories import ApprovedAICourseRepository
from apps.skills.models import Skill
from apps.students.models import Student
from . import queries
from .serializers import AchievementSerializer, SkillSerializer
from .views import AdminView


class AdminAchievements(AdminView):
    def get(self, request, id):
        get_object_or_404(Student, pk=id)
        # Matches issue_credential's eligibility rule; that service revalidates
        # under locks on every write. Prior association does not erase learning.
        rows = queries.achievements().filter(student_id=id).annotate(
            credential_count=Count('credentials', distinct=True))
        return self.listing(rows, AdminAchievementSerializer)


class AdminAchievementSerializer(AchievementSerializer):
    credential_count = serializers.IntegerField(read_only=True)

    class Meta(AchievementSerializer.Meta):
        fields = (*AchievementSerializer.Meta.fields, 'credential_count')


class AdminCatalog(AdminView):
    def get(self, request):
        return self.listing(Skill.objects.order_by('skill_code', 'pk'), SkillSerializer)


class AdminMappings(AdminView):
    def get(self, request):
        # Read the same repository as recognition. Never accept UI policy edits.
        rows = ApprovedAICourseRepository().get_approved_courses()
        return Response({'source': 'BACKEND_CONTROLLED_COURSE_MAPPINGS', 'results': [{
            key: row[key] for key in ('course_id', 'course_name', 'minimum_grade', 'skill_codes')
        } | {'enabled': row.get('enabled', True)} for row in rows]})


class AdminCredentialHistory(AdminView):
    def get(self, request, id):
        credential = get_object_or_404(Credential, pk=id)
        # Exclude actor identity, free-text reasons and authentication metadata.
        return self.listing(credential.lifecycle_events.order_by('-occurred_at', 'pk'), LifecycleSerializer)


class LifecycleSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    event_type = serializers.ChoiceField(choices=['ISSUED', 'REVOKED'])
    occurred_at = serializers.DateTimeField()
