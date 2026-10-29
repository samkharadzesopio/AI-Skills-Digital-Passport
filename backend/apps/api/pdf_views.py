"""Authenticated adapters over the existing immutable PDF document service."""
import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from rest_framework.exceptions import MethodNotAllowed, NotFound, ValidationError
from rest_framework.response import Response

from apps.accounts.authorization import get_authenticated_student_id
from apps.accounts.permissions import IsAdminWithPermission, IsOwnPassport
from apps.passports.document_services import (
    DocumentGenerationInProgress,
    generate_passport_document,
    open_passport_document_for_student,
)
from apps.passports.models import DigitalPassport, PassportDocument, PassportVersion
from passport_pdf_renderer import PDFRenderLimitError

from .pdf_serializers import PDFSelectorSerializer, pdf_status
from .pdf_throttles import PDFGenerationThrottle
from .views import PrivateView

logger = logging.getLogger(__name__)


@method_decorator(transaction.non_atomic_requests, name='dispatch')
class PDFView(PrivateView):
    operation = None
    throttle_classes = [PDFGenerationThrottle]
    http_method_names = ['get', 'post', 'head', 'options']
    administrative = False

    def should_audit(self, request):
        return super().should_audit(request) or (
            self.administrative and self.operation == 'download'
            and request.method in ('GET', 'HEAD')
        )

    def validate_input(self, request):
        allowed = {'version_id'} if self.administrative else set()
        if set(request.query_params) - allowed:
            raise ValidationError({'detail': 'Unsupported query parameter.'})
        if any(len(request.query_params.getlist(key)) != 1 for key in allowed if key in request.query_params):
            raise ValidationError({'version_id': 'Supply one version UUID.'})
        if request.method == 'POST' and request.data != {}:
            raise ValidationError({'detail': 'Send an empty JSON object; selectors belong in the URL.'})
        selector = PDFSelectorSerializer(data=request.query_params)
        selector.is_valid(raise_exception=True)
        return selector.validated_data

    def documents(self, version):
        return PassportDocument.objects.filter(passport_version=version).order_by('-generation_number')

    def metadata(self, version):
        rows = self.documents(version)
        return pdf_status(version, rows.first(), rows.filter(status='ISSUED').first())

    def post(self, request, **kwargs):
        if self.operation != 'generate':
            raise MethodNotAllowed('POST')
        selector = self.validate_input(request)
        version = self.get_version(request, selector, **kwargs)
        try:
            document = generate_passport_document(passport_version_id=version.pk, wait_seconds=0)
        except DocumentGenerationInProgress:
            return Response(self.metadata(version), status=409, headers={'Retry-After': '2'})
        except (PDFRenderLimitError, DjangoValidationError):
            result = self.metadata(version)
            result['error'] = 'PDF_NOT_REPRESENTABLE'
            return Response(result, status=422)
        except Exception:
            # The service persists failure/lease state. Never reflect provider errors.
            logger.warning('Private passport PDF generation unavailable.')
            result = self.metadata(version)
            result['error'] = 'GENERATION_UNAVAILABLE'
            return Response(result, status=503, headers={'Retry-After': '5'})
        return Response(pdf_status(version, document, document))

    def get(self, request, **kwargs):
        if self.operation not in ('status', 'download'):
            raise MethodNotAllowed(request.method)
        selector = self.validate_input(request)
        version = self.get_version(request, selector, **kwargs)
        if self.operation == 'status':
            return Response(self.metadata(version))
        rows = self.documents(version)
        document = rows.filter(status='ISSUED').first()
        if document is None:
            if rows.exists():
                return Response(self.metadata(version), status=409, headers={'Retry-After': '2'})
            raise NotFound('No PDF has been issued for this passport version.')
        try:
            _, stored_file = open_passport_document_for_student(
                document_reference=document.public_reference,
                student_id=self.owner_id(request, version),
            )
        except (OSError, PassportDocument.DoesNotExist):
            return Response({'detail': 'The stored PDF is unavailable.'}, status=503)
        except (DjangoValidationError, ValueError):
            return Response({'detail': 'The stored PDF is unavailable.'}, status=503)
        except Exception:
            logger.warning('Private passport PDF storage unavailable.')
            return Response({'detail': 'The stored PDF is unavailable.'}, status=503)
        try:
            if not self.administrative and not DigitalPassport.objects.filter(pk=version.passport_id,status='ACTIVE').exists():
                stored_file.close()
                raise NotFound('The Passport identity has been cancelled.')
            response = FileResponse(
                stored_file, as_attachment=True, content_type='application/pdf',
                filename=f'btu-passport-{version.public_reference}.pdf',
            )
            response['Pragma'] = 'no-cache'
            response['X-Content-Type-Options'] = 'nosniff'
            return response
        except Exception:
            stored_file.close()
            raise


class StudentPDFView(PDFView):
    permission_classes = [IsOwnPassport]

    def get_version(self, request, selector, id=None):
        student_id = get_authenticated_student_id(request.user)
        rows = PassportVersion.objects.select_related('passport').filter(
            passport__student_id=student_id, passport__status='ACTIVE', status='ISSUED',
        )
        if id is not None:
            version = get_object_or_404(rows, pk=id)
        else:
            passport = get_object_or_404(DigitalPassport, student_id=student_id, status='ACTIVE')
            version = get_object_or_404(rows, pk=passport.latest_version_id)
        self.check_object_permissions(request, version)
        return version

    def owner_id(self, request, version):
        return get_authenticated_student_id(request.user)


class AdminPDFView(PDFView):
    permission_classes = [IsAdminWithPermission]
    administrative = True

    def get_permissions(self):
        self.required_permission = (
            'accounts.manage_credentials' if self.request.method == 'POST'
            else 'accounts.view_student_records'
        )
        return super().get_permissions()

    def get_version(self, request, selector, id):
        passport = get_object_or_404(DigitalPassport, pk=id)
        return get_object_or_404(
            PassportVersion.objects.select_related('passport'),
            pk=selector.get('version_id', passport.latest_version_id),
            passport=passport, status='ISSUED',
        )

    def owner_id(self, request, version):
        # Admin authorization and passport/version association precede this delegation.
        return version.passport.student_id
