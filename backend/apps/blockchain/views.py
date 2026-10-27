from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.verification.views import CredentialVerificationView
from .services import document_proof


class DocumentProofView(CredentialVerificationView):
    verification_scope = 'blockchain'
    http_method_names = ['get', 'head', 'options']

    def get(self, request, document_reference):
        if request.query_params:
            raise ValidationError('No selectors are accepted.')
        return Response(document_proof(document_reference))
