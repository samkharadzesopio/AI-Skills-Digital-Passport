from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from rest_framework import serializers
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from apps.accounts.permissions import IsAdminWithPermission
from apps.passports.lifecycle import change_legal_name, revoke_passport, PassportLifecycleConflict
from apps.blockchain.chain import ProofError
from apps.passports.models import DigitalPassport, PassportLifecycleEvent
from apps.students.models import Student
from .serializers import StrictInputMixin, PassportSerializer
from .views import PrivateView, Pagination
from . import queries


class LegalNameInput(StrictInputMixin,serializers.Serializer):
    expected_passport_reference=serializers.UUIDField()
    first_name=serializers.CharField(max_length=150)
    last_name=serializers.CharField(max_length=150)
    idempotency_key=serializers.CharField(max_length=200)
    evidence_source=serializers.CharField(max_length=100)
    evidence_reference=serializers.CharField(max_length=200)
    reason=serializers.CharField(max_length=500)


class PassportRevokeInput(StrictInputMixin,serializers.Serializer):
    idempotency_key=serializers.CharField(max_length=200)
    reason=serializers.CharField(max_length=500)


@method_decorator(transaction.non_atomic_requests,name='dispatch')
class LegalNameChangeView(PrivateView):
    permission_classes=[IsAdminWithPermission]
    required_permission='accounts.manage_legal_identity'
    http_method_names=['post','options']
    def handle_exception(self,exc):
        if isinstance(exc,ProofError):
            error=APIException('Required blockchain issuer configuration is unavailable.'); error.status_code=503; exc=error
        return super().handle_exception(exc)
    def post(self,request,id):
        student=get_object_or_404(Student,pk=id)
        data=LegalNameInput(data=request.data); data.is_valid(raise_exception=True)
        try:
            event=change_legal_name(actor=request.user,student_id=student.pk,**data.validated_data)
        except PassportLifecycleConflict as exc:
            error=APIException(str(exc)); error.status_code=409; raise error
        except DigitalPassport.DoesNotExist:
            error=APIException('No current Passport is available for replacement.'); error.status_code=409; raise error
        passport=queries.passports(include_inactive=True).get(pk=event.replacement_id)
        return Response({'event_id':str(event.pk),'passport':self.render(PassportSerializer,passport)})


@method_decorator(transaction.non_atomic_requests,name='dispatch')
class PassportRevocationView(PrivateView):
    permission_classes=[IsAdminWithPermission]
    required_permission='accounts.manage_passport_lifecycle'
    http_method_names=['post','options']
    def handle_exception(self,exc):
        if isinstance(exc,ProofError):
            error=APIException('Required blockchain issuer configuration is unavailable.'); error.status_code=503; exc=error
        return super().handle_exception(exc)
    def post(self,request,id):
        passport=get_object_or_404(DigitalPassport,pk=id)
        data=PassportRevokeInput(data=request.data); data.is_valid(raise_exception=True)
        try:
            event=revoke_passport(actor=request.user,passport_reference=passport.public_reference,**data.validated_data)
        except PassportLifecycleConflict as exc:
            error=APIException(str(exc)); error.status_code=409; raise error
        return Response({'event_id':str(event.pk),'status':'REVOKED'})


class PassportLifecycleHistoryView(PrivateView):
    permission_classes=[IsAdminWithPermission]
    required_permission='accounts.manage_legal_identity'
    def should_audit(self,request):
        return True
    def get(self,request,id):
        get_object_or_404(Student,pk=id)
        pager=Pagination()
        rows=PassportLifecycleEvent.objects.filter(student_id=id).select_related('previous','replacement').order_by('-created_at','pk')
        selected=pager.paginate_queryset(rows,request,view=self)
        data=[{'id':str(row.pk),'event_type':row.event_type,'previous_reference':str(row.previous.public_reference),
               'replacement_reference':str(row.replacement.public_reference) if row.replacement else None,
               'approved_by':str(row.approved_by_id),'evidence_source':row.evidence_source,
               'evidence_reference':row.evidence_reference,'reason':row.reason,'created_at':row.created_at.isoformat()}
              for row in selected]
        return pager.get_paginated_response(data)
