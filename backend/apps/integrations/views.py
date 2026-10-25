from django.conf import settings


from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminWithPermission

from .serializers import ClassroomCompletionSerializer
from .services import ClassroomService
from .importers.excel import read_excel_completions
from .importers.google_sheets import read_google_sheet
from .importers.service import process_completion_import
from .importers.validators import ImportValidationError


class ClassroomCompletionsView(APIView):
    permission_classes = [IsAdminWithPermission]
    required_permission = "accounts.sync_classroom"

    def get(self, request):
        service = ClassroomService()
        records = service.get_completions()

        serializer = ClassroomCompletionSerializer(
            records,
            many=True
        )

        return Response({
            "source": "SIMULATED_BTU_CLASSROOM",
            "count": len(records),
            "results": serializer.data
        })


class ClassroomSyncView(APIView):
    permission_classes = [IsAdminWithPermission]
    required_permission = "accounts.sync_classroom"

    def post(self, request):
        from .classroom_automation import ClassroomCredentialAutomation
        from .serializers import ClassroomSyncControlSerializer
        controls = ClassroomSyncControlSerializer(data=request.data)
        controls.is_valid(raise_exception=True)
        dry_run = controls.validated_data['dry_run']
        result = ClassroomCredentialAutomation().synchronize(dry_run=dry_run, actor=request.user)
        return Response({
            'status': 'preview' if dry_run else 'completed',
            'source': 'SIMULATED_BTU_CLASSROOM',
            'credentials_issued': result['issued'],
            **result,
        })


class AdminExcelImportView(APIView):
    permission_classes = [IsAdminWithPermission]
    required_permission = "accounts.import_completions"
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uploaded_file = request.FILES.get("file")

        if uploaded_file is None:
            return Response(
                {"error": "Excel file is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not uploaded_file.name.lower().endswith(".xlsx"):
            return Response(
                {"error": "Only .xlsx files are supported"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            records, validation_errors = (
                read_excel_completions(uploaded_file)
            )

            result = process_completion_import(
                records,
                source="BTU_EXCEL",
            )

        except ImportValidationError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({
            "source": "BTU_EXCEL",
            "result": result,
            "validation_errors": validation_errors,
        })


class AdminGoogleSheetsImportView(APIView):
    permission_classes = [IsAdminWithPermission]
    required_permission = "accounts.import_completions"

    def post(self, request):
        # Only server-configured spreadsheets are trusted.
        spreadsheet_id = getattr(
            settings, "BTU_GOOGLE_SHEET_ID", None
        )

        if not spreadsheet_id:
            return Response(
                {"error": "Google Sheets is not configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            records, validation_errors = read_google_sheet(
                spreadsheet_id=spreadsheet_id,
            )

            result = process_completion_import(
                records,
                source="BTU_GOOGLE_SHEETS",
            )

        except ImportValidationError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            return Response(
                {"error": "Google Sheets import failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({
            "source": "BTU_GOOGLE_SHEETS",
            "result": result,
            "validation_errors": validation_errors,
        })


class ClassroomSyncHistoryView(APIView):
    permission_classes = [IsAdminWithPermission]
    required_permission = 'accounts.sync_classroom'

    def get(self, request):
        from .models import ClassroomSyncEvent
        from rest_framework.pagination import CursorPagination
        pagination = CursorPagination()
        pagination.page_size = 50
        pagination.ordering = '-created_at'
        rows = pagination.paginate_queryset(ClassroomSyncEvent.objects.all(), request)
        return pagination.get_paginated_response([{
            'id': str(row.pk), 'source': row.source, 'source_event_id': row.source_event_id,
            'state': row.state, 'attempts': row.attempts, 'retryable': row.retryable,
            'next_retry_at': row.next_retry_at, 'error_code': row.error_code,
            'credential_id': str(row.credential_id) if row.credential_id else None,
        } for row in rows])


class ClassroomSyncRetryView(APIView):
    permission_classes = [IsAdminWithPermission]
    required_permission = 'accounts.sync_classroom'

    def post(self, request, event_id):
        from django.shortcuts import get_object_or_404
        from .classroom_automation import process_event
        from .models import ClassroomSyncEvent
        if request.data:
            return Response({'detail': 'Retry accepts no replacement event data.'}, status=400)
        event = get_object_or_404(ClassroomSyncEvent, pk=event_id)
        result = process_event(event.pk, force=True)
        event.refresh_from_db()
        return Response({'result': result, 'state': event.state,
                         'attempts': event.attempts, 'error_code': event.error_code})
