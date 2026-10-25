from rest_framework.views import APIView
from .models import SecurityAudit
from .otp_utils import normalize_client_ip, security_digest


class AuditedAPIView(APIView):
    """Record attempts before execution, outcomes without request/response bodies."""
    def _audit(self, request):
        user = getattr(request, '_user', None)
        return SecurityAudit.objects.create(
            actor=user if getattr(user, 'is_authenticated', False) and getattr(user, 'pk', None) else None,
            action=f'{self.__class__.__name__}:{request.method}',
            ip_digest=security_digest('security.audit.ip', normalize_client_ip(request.META.get('REMOTE_ADDR'))),
        )

    def should_audit(self, request):
        return request.method not in ('GET', 'HEAD', 'OPTIONS')

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if self.should_audit(request):
            self.audit_record = self._audit(request)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        if self.should_audit(request):
            row = getattr(self, 'audit_record', None) or self._audit(request)
            SecurityAudit.objects.filter(pk=row.pk).update(status_code=response.status_code)
        return response
