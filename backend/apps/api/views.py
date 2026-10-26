"""Student and administrator adapters over the existing institutional domain."""
from django.core.exceptions import ValidationError as DjangoValidationError, ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import APIException, ValidationError, MethodNotAllowed
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from apps.accounts.audit import AuditedAPIView
from apps.accounts.authorization import get_authenticated_student_id
from apps.accounts.permissions import IsStudent, IsAdminWithPermission, IsOwnCredential, IsOwnPassport
from apps.students.models import Student
from apps.credentials.models import BTU_ISSUER_REFERENCE
from apps.credentials.services import issue_credential, revoke_credential, IdempotencyConflict
from . import queries as q
from .serializers import (StudentSerializer, SkillSerializer, RecognizedSkillSerializer, AchievementSerializer, CredentialSerializer, PassportSerializer, VersionSerializer, IssueSerializer, RevokeSerializer)


class Pagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class PrivateView(AuditedAPIView):
    http_method_names = ['get', 'head', 'options']

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.now = timezone.now()

    def render(self, serializer, obj, **kwargs):
        return serializer(obj, context={'now': self.now}, **kwargs).data

    def listing(self, queryset, serializer):
        pagination = Pagination()
        rows = pagination.paginate_queryset(queryset, self.request, view=self)
        return pagination.get_paginated_response(self.render(serializer, rows, many=True))

    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            exc = ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)
        elif isinstance(exc, IdempotencyConflict):
            error = APIException(str(exc)); error.status_code = 409; exc = error
        elif isinstance(exc, ImproperlyConfigured):
            error = APIException('Required institutional service is not configured.'); error.status_code = 503; exc = error
        return super().handle_exception(exc)


def uuid_parameter(request, name):
    raw = request.query_params.get(name)
    return serializers.UUIDField().run_validation(raw) if raw is not None else None


def current_passport_summary(student_id,render):
    from apps.passports.models import DigitalPassport
    for _ in range(2):
        passport=q.passports().filter(student_id=student_id).first()
        if passport is None:
            return None
        data=render(PassportSerializer,passport)
        if DigitalPassport.objects.filter(pk=passport.pk,status='ACTIVE').exists():
            return data
    error=APIException('Current Passport changed; retry the request.'); error.status_code=409; raise error


def student_summary(student_id, now, render):
    awards = q.achievements().filter(student_id=student_id)
    skills = q.recognized_skills(student_id)
    credentials = q.credentials().filter(student_id=student_id)
    passport = current_passport_summary(student_id,render)
    return {
        'profile': StudentSerializer(Student.objects.get(pk=student_id)).data,
        'recognized_skills': skills.count(),
        'skills_by_category': q.skill_distribution(skills, 'category'),
        'skills_by_subcategory': q.skill_distribution(skills, 'subcategory'),
        'verified_achievements': awards.count(),
        'credentials': q.credential_counts(credentials, now),
        'recent_achievements': render(AchievementSerializer, awards[:5], many=True),
        'recent_credentials': render(CredentialSerializer, credentials[:5], many=True),
        'passport': passport,
    }


class StudentView(PrivateView):
    permission_classes = [IsStudent]
    resource = None

    def get_permissions(self):
        if self.resource == 'credentials':
            return [IsOwnCredential()]
        if self.resource in ('passport', 'versions'):
            return [IsOwnPassport()]
        return super().get_permissions()

    def detail(self, rows, serializer, id):
        obj = get_object_or_404(rows, pk=id)
        self.check_object_permissions(self.request, obj)
        return Response(self.render(serializer, obj))

    def get(self, request, id=None):
        student_id = get_authenticated_student_id(request.user)
        if self.resource == 'dashboard':
            return Response(student_summary(student_id, self.now, self.render))
        if self.resource == 'skills':
            return self.listing(q.recognized_skills(student_id), RecognizedSkillSerializer)
        if self.resource == 'achievements':
            rows = q.achievements().filter(student_id=student_id)
            skill_id = uuid_parameter(request, 'skill_id')
            if skill_id:
                rows = rows.filter(skill_id=skill_id)
            return self.listing(rows, AchievementSerializer)
        if self.resource == 'credentials':
            rows = q.credentials().filter(student_id=student_id)
            return self.detail(rows, CredentialSerializer, id) if id else self.listing(rows, CredentialSerializer)
        if self.resource == 'passport':
            passport=current_passport_summary(student_id,self.render)
            return Response(passport if passport else {'passport': None})
        rows = q.versions().filter(passport__student_id=student_id)
        return self.detail(rows, VersionSerializer, id) if id else self.listing(rows, VersionSerializer)


class AdminView(PrivateView):
    permission_classes = [IsAdminWithPermission]
    required_permission = 'accounts.view_student_records'


class AdminStudents(AdminView):
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_permissions(self):
        self.required_permission = 'accounts.manage_student_accounts' if self.request.method in ('POST', 'PATCH') else 'accounts.view_student_records'
        return super().get_permissions()

    def get(self, request, id=None):
        if id:
            get_object_or_404(Student, pk=id)
            return Response(student_summary(id, self.now, self.render))
        rows = Student.objects.order_by('external_student_id', 'pk')
        search = request.query_params.get('search', '').strip()
        if len(search) > 150:
            raise ValidationError({'search': 'At most 150 characters.'})
        if search:
            rows = rows.filter(Q(external_student_id__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(email__icontains=search))
        for field in ('program', 'education_level', 'student_status'):
            if field in request.query_params:
                rows = rows.filter(**{field: request.query_params[field]})
        return self.listing(rows, StudentSerializer)

    def write(self, request, id=None):
        try:
            with transaction.atomic():
                instance = get_object_or_404(Student.objects.select_for_update(), pk=id) if id else None
                serializer = StudentSerializer(instance, data=request.data, partial=bool(id))
                serializer.is_valid(raise_exception=True)
                serializer.save()
                return Response(serializer.data, status=200 if id else 201)
        except IntegrityError:
            raise ValidationError({'detail': 'Student conflicts with an existing university record or violates a record constraint.'}) from None

    def post(self, request, id=None):
        if id is not None:
            raise MethodNotAllowed('POST')
        return self.write(request)

    def patch(self, request, id=None):
        if id is None:
            raise MethodNotAllowed('PATCH')
        return self.write(request, id)


class AdminCredentials(AdminView):
    def get(self, request, id=None):
        rows = q.credentials()
        student_id = uuid_parameter(request, 'student_id')
        if student_id:
            rows = rows.filter(student_id=student_id)
        status = request.query_params.get('status')
        if status:
            filters = q.validity_filters(self.now)
            if status == 'ISSUED':
                rows = rows.filter(status='ISSUED')
            elif status in filters:
                rows = rows.filter(filters[status])
            else:
                raise ValidationError({'status': 'Use ISSUED, VALID, EXPIRED, REVOKED, or INVALID.'})
        return Response(self.render(CredentialSerializer, get_object_or_404(rows, pk=id))) if id else self.listing(rows, CredentialSerializer)


class AdminIssue(AdminView):
    required_permission = 'accounts.manage_credentials'
    http_method_names = ['post', 'options']

    def post(self, request):
        data = IssueSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            credential = issue_credential(issuer_reference=BTU_ISSUER_REFERENCE, **data.validated_data)
        credential = q.credentials().get(pk=credential.pk)
        # 200 for both first issuance and replay: idempotent operation contract.
        return Response(self.render(CredentialSerializer, credential))


class AdminRevoke(AdminView):
    required_permission = 'accounts.revoke_credentials'
    http_method_names = ['post', 'options']

    def post(self, request, id):
        credential = get_object_or_404(q.credentials(), pk=id)
        data = RevokeSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        with transaction.atomic():
            credential = revoke_credential(public_reference=credential.public_reference, actor=request.user, **data.validated_data)
        return Response(self.render(CredentialSerializer, q.credentials().get(pk=credential.pk)))


class AdminPassports(AdminView):
    def get(self, request, id=None, versions=False):
        rows = q.passports(include_inactive=True)
        student_id = uuid_parameter(request, 'student_id')
        if student_id:
            rows = rows.filter(student_id=student_id)
        if id:
            passport = get_object_or_404(rows, pk=id)
            if versions:
                from apps.passports.models import PassportVersion
                return self.listing(PassportVersion.objects.filter(passport=passport,status='ISSUED').select_related('passport').prefetch_related('skill_snapshots','credential_snapshots').order_by('-version_number'), VersionSerializer)
            return Response(self.render(PassportSerializer, passport))
        return self.listing(rows, PassportSerializer)


class AdminStatistics(AdminView):
    def get(self, request):
        skills = q.recognized_skills()
        return Response({
            'students': Student.objects.count(),
            'credentials': q.credential_counts(q.credentials(), self.now),
            'passports': q.passports().count(),
            'recognized_skills': skills.count(),
            'skills_by_category': q.skill_distribution(skills, 'category'),
            'skills_by_subcategory': q.skill_distribution(skills, 'subcategory'),
            'verified_achievements': q.achievements().count(),
        })
