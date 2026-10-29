"""Existing importing administrators opt into approved source discovery only."""
from django.shortcuts import get_object_or_404
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from .models import SpreadsheetAutomation, SpreadsheetPoll, SpreadsheetProfile
from .spreadsheet_views import SourceView
from .spreadsheet_automation import configure_automation
from .importers.preview import ImportProblem


def public_source(profile, binding=None):
    return {'profile_id': str(profile.pk), 'profile_key': profile.key, 'profile_version': profile.version, 'profile_enabled': profile.enabled,
        'enabled': bool(binding and binding.enabled), 'interval_seconds': binding.interval_seconds if binding else 300,
        'state': binding.last_state if binding else 'IDLE', 'error_code': binding.last_error_code if binding else '',
        'last_checked_at': binding.last_checked_at if binding else None,
        'next_poll_at': binding.next_poll_at if binding and binding.enabled else None}


class AutomaticSourcesView(SourceView):
    def get(self, request):
        pager = PageNumberPagination(); pager.page_size = 50
        profiles = pager.paginate_queryset(SpreadsheetProfile.objects.filter(
            source='BTU_GOOGLE_SHEETS', kind='SKILL_AWARD').filter(Q(enabled=True) | Q(automation__isnull=False))
            .select_related('automation').order_by('key', 'version'), request)
        return pager.get_paginated_response([public_source(p, getattr(p, 'automation', None)) for p in profiles])


class AutomaticSourceView(SourceView):
    parser_classes = [JSONParser]

    def post(self, request, profile_id):
        profile = get_object_or_404(SpreadsheetProfile, pk=profile_id, source='BTU_GOOGLE_SHEETS', kind='SKILL_AWARD')
        body = request.data
        valid = isinstance(body, dict) and type(body.get('enabled')) is bool
        expected = {'enabled', 'confirm', 'interval_seconds', 'authorization_reference'} if valid and body['enabled'] else {'enabled'}
        if not valid or set(body) != expected or (body['enabled'] and body['confirm'] is not True):
            raise ImportProblem('INVALID_AUTOMATION_CONTROL', 400)
        binding = configure_automation(profile.pk, actor=request.user, enabled=body['enabled'],
            interval_seconds=body.get('interval_seconds', 300), authorization_reference=body.get('authorization_reference', ''))
        return Response(public_source(profile, binding))


class AutomaticHistoryView(SourceView):
    def get(self, request, profile_id):
        get_object_or_404(SpreadsheetProfile, pk=profile_id, source='BTU_GOOGLE_SHEETS', kind='SKILL_AWARD')
        pager = PageNumberPagination(); pager.page_size = 50
        rows = pager.paginate_queryset(SpreadsheetPoll.objects.filter(automation__profile_id=profile_id).order_by('-started_at'), request)
        return pager.get_paginated_response([{'id': str(p.pk), 'state': p.state, 'counts': p.counts,
            'error_code': p.error_code, 'started_at': p.started_at, 'finished_at': p.finished_at,
            'preview_id': str(p.preview_id) if p.preview_id else None} for p in rows])
