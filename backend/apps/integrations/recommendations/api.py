from datetime import timedelta
from django.core.exceptions import ImproperlyConfigured
from django.db import connection, transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.throttling import BaseThrottle
from rest_framework.views import APIView
from apps.accounts.authorization import get_authenticated_student_id
from apps.accounts.models import AuthRateLimitBucket
from apps.accounts.otp_utils import security_digest
from apps.accounts.permissions import IsStudent
from .contracts import CATEGORIES, INTERESTS, LEVELS, Options
from .service import RecommendationService


class RecommendationUnavailable(APIException):
    status_code = 503
    default_detail = 'Academic recommendations are temporarily unavailable.'


class Filters(serializers.Serializer):
    category = serializers.ChoiceField(choices=CATEGORIES, required=False)
    interest = serializers.ChoiceField(choices=INTERESTS, required=False)
    difficulty = serializers.ChoiceField(choices=list(LEVELS), required=False)
    limit = serializers.IntegerField(min_value=1, max_value=10, default=5)
    include_future_pathway = serializers.BooleanField(default=True)

    def to_internal_value(self, data):
        if set(data) - set(self.fields) or any(len(data.getlist(k)) > 1 for k in data):
            raise serializers.ValidationError({'filters': 'Unknown or duplicate filters are not accepted.'})
        return super().to_internal_value(data)


class RecommendationThrottle(BaseThrottle):
    def allow_request(self, request, view):
        if connection.vendor != 'postgresql':
            raise ImproperlyConfigured('Recommendation limits require PostgreSQL.')
        # Permissions have already validated the persisted Student identity.
        key = security_digest('recommendations.rate.v1', str(request.user.pk))
        with transaction.atomic():
            AuthRateLimitBucket.objects.get_or_create(bucket_digest=key)
            row = AuthRateLimitBucket.objects.select_for_update().get(pk=key)
            now = timezone.now()
            if now - row.window_started_at >= timedelta(minutes=1):
                row.window_started_at, row.request_count = now, 0
            self.remaining = max(1, 60 - (now - row.window_started_at).total_seconds())
            if row.request_count >= 30:
                return False
            row.request_count += 1
            row.save(update_fields=['window_started_at', 'request_count', 'updated_at'])
        return True

    def wait(self):
        return self.remaining


class CourseRecommendationsView(APIView):
    permission_classes = [IsStudent]
    throttle_classes = [RecommendationThrottle]

    def get(self, request):
        filters = Filters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        student_id = get_authenticated_student_id(request.user)
        try:
            result = RecommendationService().recommend(student_id, Options(**filters.validated_data))
        except Exception:
            # No grades, profiles, provider text or internal errors enter logs/responses.
            raise RecommendationUnavailable() from None
        return Response(result)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        response['Vary'] = 'Cookie'
        return response
