"""Additive v1 preview workflow. The existing strict imports remain compatible."""
from uuid import UUID

from django.shortcuts import get_object_or_404
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from apps.accounts.audit import AuditedAPIView
from apps.accounts.permissions import IsAdminWithPermission
from .models import SpreadsheetPreview, SpreadsheetProfile
from .importers.mapping import excel_grid
from .importers.preview import ImportProblem, confirm_preview, create_preview, public_preview
from .importers.sheet_source import SheetUnavailable, read_profile_sheet
from .importers.validators import ImportValidationError


class SourceView(AuditedAPIView):
    permission_classes = [IsAdminWithPermission]
    required_permission = 'accounts.import_completions'

    def handle_exception(self, exc):
        if isinstance(exc, ImportValidationError):
            code = exc.code if isinstance(exc, ImportProblem) else ('GOOGLE_SOURCE_UNAVAILABLE' if isinstance(exc, SheetUnavailable) else 'INVALID_SPREADSHEET_OR_MAPPING')
            return Response({'code': code, 'detail': str(exc) if not isinstance(exc, ImportProblem) else code},
                            status=exc.status if isinstance(exc, ImportProblem) else (503 if isinstance(exc, SheetUnavailable) else 400))
        return super().handle_exception(exc)


class ProfileListView(SourceView):
    def get(self, request):
        from rest_framework.pagination import PageNumberPagination
        pager = PageNumberPagination()
        pager.page_size = 50
        rows = pager.paginate_queryset(SpreadsheetProfile.objects.filter(enabled=True).order_by('key', 'version'), request)
        return pager.get_paginated_response([{'id': str(p.pk), 'key': p.key, 'version': p.version,
            'source': p.source, 'kind': p.kind} for p in rows])


class ExcelPreviewView(SourceView):
    parser_classes = [MultiPartParser, FormParser]
    source = 'BTU_EXCEL'

    def initial(self, request, *args, **kwargs):
        from apps.verification.security import install_upload_limits
        install_upload_limits(request)
        super().initial(request, *args, **kwargs)

    def post(self, request):
        if set(request.data) != {'profile_id', 'file'} or len(request.data.getlist('profile_id')) != 1 or len(request.FILES.getlist('file')) != 1:
            raise ImportValidationError('Supply exactly one profile_id and one file.')
        profile = lookup_profile(request.data.get('profile_id'), 'BTU_EXCEL')
        from .importers.preview import check_profile
        check_profile(profile)
        file = request.FILES.get('file')
        if not file or not file.name.lower().endswith('.xlsx'):
            raise ImportValidationError('A nonempty .xlsx file is required.')
        rows, hashed = excel_grid(file, worksheet=profile.definition.get('worksheet', 'Completions'))
        return Response(public_preview(create_preview(profile, rows, hashed, actor=request.user)), status=201)


def lookup_profile(value, source):
    try:
        value = UUID(str(value))
    except (TypeError, ValueError):
        raise ImportValidationError('Invalid profile_id.') from None
    return get_object_or_404(SpreadsheetProfile, pk=value, source=source, enabled=True)


class GooglePreviewView(SourceView):
    parser_classes = [JSONParser]

    def post(self, request):
        if not isinstance(request.data, dict) or set(request.data) != {'profile_id'}:
            raise ImportValidationError('Supply only the approved profile_id; source URLs and IDs are not accepted.')
        profile = lookup_profile(request.data['profile_id'], 'BTU_GOOGLE_SHEETS')
        from .importers.preview import check_profile
        check_profile(profile)
        rows, hashed = read_profile_sheet(profile)
        return Response(public_preview(create_preview(profile, rows, hashed, actor=request.user)), status=201)


class PreviewDetailView(SourceView):
    def get(self, request, preview_id):
        preview = get_object_or_404(SpreadsheetPreview.objects.select_related('run'), pk=preview_id, actor=request.user)
        return Response(public_preview(preview))


class PreviewConfirmView(SourceView):
    parser_classes = [JSONParser]

    def post(self, request, preview_id):
        if not isinstance(request.data, dict) or set(request.data) != {'snapshot_sha256', 'confirm'} or request.data['confirm'] is not True:
            raise ImportValidationError('Explicit confirm:true and the reviewed snapshot_sha256 are required.')
        get_object_or_404(SpreadsheetPreview, pk=preview_id, actor=request.user)
        result = confirm_preview(preview_id, request.data['snapshot_sha256'], actor=request.user)
        return Response(public_preview(result))
