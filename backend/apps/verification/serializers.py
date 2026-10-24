
from rest_framework import serializers


class CredentialVerificationSerializer(serializers.Serializer):
    credential_id = serializers.CharField()
    status = serializers.ChoiceField(
        choices=[
            "VALID",
            "REVOKED",
            "EXPIRED",
            "INVALID",
            "NOT_FOUND",
        ]
    )
    verified = serializers.BooleanField()
    source = serializers.CharField()
