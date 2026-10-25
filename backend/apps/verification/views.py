
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .services import CredentialVerificationService
from .serializers import CredentialVerificationSerializer
from .security import VerificationThrottle, install_upload_limits


class CredentialVerificationView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [VerificationThrottle]
    verification_scope = 'credential'

    def get(self, request, credential_id):
        service = CredentialVerificationService()
        result = service.verify(credential_id)

        serializer = CredentialVerificationSerializer(result)
        return Response(serializer.data)

from rest_framework.parsers import MultiPartParser
from rest_framework import status

from .document_service import DocumentVerificationService
from .document_serializers import (
    DocumentUploadSerializer,
    DocumentVerificationResultSerializer,
)


class DocumentVerificationView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [VerificationThrottle]
    verification_scope = 'pdf'

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        install_upload_limits(request)
    parser_classes = [MultiPartParser]

    def post(self, request):
        upload_serializer = DocumentUploadSerializer(
            data=request.data
        )

        upload_serializer.is_valid(
            raise_exception=True
        )

        uploaded_file = (
            upload_serializer.validated_data["file"]
        )

        service = DocumentVerificationService()
        result = service.verify(uploaded_file)

        response_serializer = (
            DocumentVerificationResultSerializer(
                result
            )
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )
