"""Private PDF metadata; storage, leases, and raw service errors stay internal."""
from rest_framework import serializers


class PDFSelectorSerializer(serializers.Serializer):
    version_id = serializers.UUIDField(required=False)


class PDFStatusSerializer(serializers.Serializer):
    document_reference = serializers.UUIDField(allow_null=True)
    passport_reference = serializers.UUIDField()
    passport_version_reference = serializers.UUIDField()
    status = serializers.ChoiceField(
        choices=['NOT_REQUESTED', 'PENDING', 'GENERATING', 'ISSUED', 'FAILED']
    )
    generated_at = serializers.DateTimeField(allow_null=True)
    available_for_download = serializers.BooleanField()
    download_document_reference = serializers.UUIDField(allow_null=True)
    error = serializers.CharField(allow_null=True)


def pdf_status(version, document, downloadable):
    return PDFStatusSerializer({
        'document_reference': document.public_reference if document else None,
        'passport_reference': version.passport.public_reference,
        'passport_version_reference': version.public_reference,
        'status': document.status if document else 'NOT_REQUESTED',
        'generated_at': document.generated_at if document else None,
        'available_for_download': downloadable is not None,
        'download_document_reference': downloadable.public_reference if downloadable else None,
        'error': 'GENERATION_FAILED' if document and document.status == 'FAILED' else None,
    }).data
