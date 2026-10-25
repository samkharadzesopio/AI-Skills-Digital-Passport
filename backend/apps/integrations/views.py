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
        service = ClassroomService()
        eligible = service.get_eligible_completions()

        if request.data.get("dry_run") is not True:
            return Response(
                {
                    "status": "not_configured",
                    "detail": (
                        "Live synchronization requires "
                        "credential issuance and a durable ledger."
                    ),
                },
                status=503,
            )

        return Response({
            "status": "preview",
            "source": "SIMULATED_BTU_CLASSROOM",
            "eligible_count": len(eligible),
            "eligible_event_ids": [
                record["event_id"] for record in eligible
            ],
            "credentials_issued": 0,
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
