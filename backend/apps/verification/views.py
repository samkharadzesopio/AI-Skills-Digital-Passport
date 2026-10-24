
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .services import CredentialVerificationService
from .serializers import CredentialVerificationSerializer


class CredentialVerificationView(APIView):
    permission_classes = [AllowAny]

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
    permission_classes = [AllowAny]
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
