from apps.accounts.audit import AuditedAPIView
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


class ClassroomCompletionsView(AuditedAPIView):
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


class ClassroomSyncView(AuditedAPIView):
    permission_classes = [IsAdminWithPermission]
    required_permission = "accounts.sync_classroom"

    def should_audit(self, request):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return False
        from apps.accounts.authorization import has_admin_permission
        # Never parse an unauthorized body just to record its denial.
        if not has_admin_permission(getattr(request, '_user', None), self.required_permission):
            return True
        from rest_framework.exceptions import APIException
        from .serializers import ClassroomSyncControlSerializer
        try:
            controls = ClassroomSyncControlSerializer(data=request.data)
            return not (controls.is_valid() and controls.validated_data['dry_run'])
        except APIException:
            return True

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


class AdminExcelImportView(AuditedAPIView):
    permission_classes = [IsAdminWithPermission]
    required_permission = "accounts.import_completions"
    parser_classes = [MultiPartParser, FormParser]

    def initial(self, request, *args, **kwargs):
        # Install before session CSRF processing can inspect multipart form fields.
        from apps.verification.security import install_upload_limits
        install_upload_limits(request)
        super().initial(request, *args, **kwargs)

    def post(self, request):
        uploaded_file = request.FILES.get("file")

        # An explicit saved profile selects the additive preview/confirmation
        # workflow. Omitting it retains the original strict completion contract.
        if 'profile_id' in request.data:
            from .spreadsheet_views import ExcelPreviewView
            from .importers.preview import ImportProblem
            try:
                return ExcelPreviewView.post(self, request)
            except ImportValidationError as exc:
                return Response({'code': exc.code if isinstance(exc, ImportProblem) else 'INVALID_SPREADSHEET_OR_MAPPING'},
                                status=exc.status if isinstance(exc, ImportProblem) else 400)

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

        from .importers.durable import require_source
        from .models import ImportRun
        try:
            require_source('BTU_EXCEL')
        except ValueError:
            return Response({'error': 'Institutional source is not authorized for credential issuance.'}, status=503)
        run = ImportRun.objects.create(source='BTU_EXCEL', actor=request.user)
        try:
            records, validation_errors = (
                read_excel_completions(uploaded_file)
            )

            result = process_completion_import(
                records,
                source="BTU_EXCEL", actor=request.user, run=run,
            )

        except ImportValidationError as exc:
            run.state, run.summary = 'FAILED', {'error': 'IMPORT_VALIDATION_FAILED'}
            from django.utils import timezone
            run.finished_at = timezone.now()
            run.save()
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except Exception:
            from django.utils import timezone
            run.state, run.summary = 'FAILED', {'error': 'IMPORT_PROCESSING_FAILED'}
            run.finished_at = timezone.now()
            run.save()
            return Response({'error': 'Import processing failed.'}, status=502)

        run.refresh_from_db()
        run.validation_errors = [{'row': e.get('row'), 'code': 'INVALID_ROW'} for e in validation_errors]
        if validation_errors:
            run.state = 'PARTIAL' if records else 'FAILED'
        run.save(update_fields=['validation_errors', 'state'])
        return Response({
            "source": "BTU_EXCEL",
            "result": result,
            "validation_errors": validation_errors,
        })


class AdminGoogleSheetsImportView(AuditedAPIView):
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

        from .importers.durable import require_source
        from .models import ImportRun
        try:
            require_source('BTU_GOOGLE_SHEETS')
        except ValueError:
            return Response({'error': 'Institutional source is not authorized for credential issuance.'}, status=503)
        run = ImportRun.objects.create(source='BTU_GOOGLE_SHEETS', actor=request.user)
        try:
            records, validation_errors = read_google_sheet(
                spreadsheet_id=spreadsheet_id,
            )

            result = process_completion_import(
                records,
                source="BTU_GOOGLE_SHEETS", actor=request.user, run=run,
            )

        except ImportValidationError as exc:
            run.state, run.summary = 'FAILED', {'error': 'IMPORT_VALIDATION_FAILED'}
            from django.utils import timezone
            run.finished_at = timezone.now()
            run.save()
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            run.state, run.summary = 'FAILED', {'error': 'SOURCE_UNAVAILABLE'}
            from django.utils import timezone
            run.finished_at = timezone.now()
            run.save()
            return Response(
                {"error": "Google Sheets import failed"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        run.refresh_from_db()
        run.validation_errors = [{'row': e.get('row'), 'code': 'INVALID_ROW'} for e in validation_errors]
        if validation_errors:
            run.state = 'PARTIAL' if records else 'FAILED'
        run.save(update_fields=['validation_errors', 'state'])
        return Response({
            "source": "BTU_GOOGLE_SHEETS",
            "result": result,
            "validation_errors": validation_errors,
        })


class ClassroomSyncHistoryView(AuditedAPIView):
    permission_classes = [IsAdminWithPermission]
    required_permission = 'accounts.sync_classroom'

    def get(self, request):
        from .models import ClassroomSyncEvent
        from rest_framework.pagination import CursorPagination
        pagination = CursorPagination()
        pagination.page_size = 50
        pagination.ordering = '-created_at'
        rows = pagination.paginate_queryset(ClassroomSyncEvent.objects.filter(source='BTU_CLASSROOM'), request)
        return pagination.get_paginated_response([{
            'id': str(row.pk), 'source': row.source, 'source_event_id': row.source_event_id,
            'state': row.state, 'attempts': row.attempts, 'retryable': row.retryable,
            'next_retry_at': row.next_retry_at, 'error_code': row.error_code,
            'credential_id': str(row.credential_id) if row.credential_id else None,
        } for row in rows])


class ClassroomSyncRetryView(AuditedAPIView):
    permission_classes = [IsAdminWithPermission]
    required_permission = 'accounts.sync_classroom'

    def post(self, request, event_id):
        from django.shortcuts import get_object_or_404
        from .classroom_automation import process_event
        from .models import ClassroomSyncEvent
        if request.data:
            return Response({'detail': 'Retry accepts no replacement event data.'}, status=400)
        event = get_object_or_404(ClassroomSyncEvent.objects.filter(source='BTU_CLASSROOM'), pk=event_id)
        result = process_event(event.pk, force=True)
        event.refresh_from_db()
        return Response({'result': result, 'state': event.state,
                         'attempts': event.attempts, 'error_code': event.error_code})


class ImportHistoryView(AuditedAPIView):
    permission_classes = [IsAdminWithPermission]
    required_permission = 'accounts.import_completions'

    def get(self, request):
        from rest_framework.pagination import CursorPagination
        from .models import ImportRun
        pager = CursorPagination()
        pager.page_size, pager.ordering = 50, '-created_at'
        rows = pager.paginate_queryset(ImportRun.objects.order_by('-created_at'), request)
        return pager.get_paginated_response([{
            'id': row.pk, 'source': row.source, 'state': row.state,
            'summary': row.summary, 'validation_errors': row.validation_errors,
        } for row in rows])


class ImportRetryView(AuditedAPIView):
    permission_classes = [IsAdminWithPermission]
    required_permission = 'accounts.import_completions'

    def post(self, request, event_id):
        from django.shortcuts import get_object_or_404
        from .models import ClassroomSyncEvent
        from .classroom_automation import process_event
        if request.data:
            return Response({'detail': 'Retry accepts no replacement data.'}, status=400)
        row = get_object_or_404(ClassroomSyncEvent.objects.filter(source__in=['BTU_EXCEL', 'BTU_GOOGLE_SHEETS']), pk=event_id)
        outcome = process_event(row.pk, force=True)
        row.refresh_from_db()
        # Keep the derived run history current after the existing event replay.
        # Reconciliation reads persisted outcomes; it never accepts replacement
        # evidence or changes the recognition/idempotency rules.
        from django.db import transaction
        from .importers.durable import reconcile_run
        from .models import ImportRun
        with transaction.atomic():
            for run in ImportRun.objects.select_for_update().filter(events=row).order_by('pk'):
                reconcile_run(run)
        return Response({'result': outcome, 'state': row.state, 'error_code': row.error_code})


class ImportEventsView(AuditedAPIView):
    """Bounded event identifiers needed by the existing import retry contract."""
    permission_classes = [IsAdminWithPermission]
    required_permission = 'accounts.import_completions'

    def get(self, request, run_id):
        from django.shortcuts import get_object_or_404
        from rest_framework.pagination import CursorPagination
        from .models import ImportRun
        run = get_object_or_404(ImportRun, pk=run_id)
        pager = CursorPagination()
        pager.page_size, pager.ordering = 50, '-created_at'
        rows = pager.paginate_queryset(run.events.filter(source__in=['BTU_EXCEL', 'BTU_GOOGLE_SHEETS']), request)
        return pager.get_paginated_response([{
            'id': str(row.pk), 'source': row.source, 'source_event_id': row.source_event_id,
            'state': row.state, 'attempts': row.attempts, 'retryable': row.retryable,
            'next_retry_at': row.next_retry_at, 'error_code': row.error_code,
            'credential_id': str(row.credential_id) if row.credential_id else None,
        } for row in rows])
