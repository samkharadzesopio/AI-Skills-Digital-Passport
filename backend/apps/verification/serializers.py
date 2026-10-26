
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


class PassportVerificationSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['VALID', 'OUTDATED', 'REVOKED', 'REPLACED', 'PENDING_BLOCKCHAIN', 'EXPIRED', 'INVALID', 'NOT_FOUND', 'UNVERIFIABLE'])
    authentic = serializers.BooleanField()
    is_latest = serializers.BooleanField(allow_null=True)
    passport_version = serializers.IntegerField(allow_null=True)
    latest_version = serializers.IntegerField(allow_null=True)
    credential_status = serializers.ChoiceField(choices=['VALID', 'REVOKED', 'EXPIRED', 'INVALID', 'UNVERIFIABLE'])
    credential_counts = serializers.DictField(child=serializers.IntegerField(min_value=0))
    source = serializers.CharField()
    blockchain = serializers.DictField(required=False)
