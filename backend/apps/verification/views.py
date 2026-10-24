
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
