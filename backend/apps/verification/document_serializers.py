
from rest_framework import serializers


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField(
        allow_empty_file=False
    )


class DocumentVerificationResultSerializer(
    serializers.Serializer
):
    status = serializers.ChoiceField(
        choices=[
            "VALID",
            "OUTDATED",
            "INVALID",
            "UNVERIFIABLE",
            "REVOKED",
            "EXPIRED",
            "REPLACED",
            "PENDING_BLOCKCHAIN",
        ]
    )
    authentic = serializers.BooleanField()
    is_latest = serializers.BooleanField(
        allow_null=True
    )
    passport_version = serializers.IntegerField(
        allow_null=True
    )
    latest_version = serializers.IntegerField(
        allow_null=True
    )
    message = serializers.CharField()
    source = serializers.CharField()

    credential_status = serializers.ChoiceField(choices=['VALID', 'REVOKED', 'EXPIRED', 'INVALID', 'UNVERIFIABLE'])
    credential_counts = serializers.DictField(child=serializers.IntegerField(min_value=0))
    # Registry validity is separate from live chain proof and institutional identity.
    blockchain = serializers.DictField(required=False)
