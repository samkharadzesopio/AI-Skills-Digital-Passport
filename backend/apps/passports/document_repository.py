from uuid import UUID

from .models import DigitalPassport, PassportDocument


class PassportDocumentRepository:
    """Database adapter matching the existing document-verification contract."""

    def find_by_hash(self, pdf_hash):
        document = (
            PassportDocument.objects.select_related("passport_version__passport")
            .filter(pdf_sha256=pdf_hash, status=PassportDocument.Status.ISSUED)
            .first()
        )
        if document is None:
            return None
        return {
            "document_id": str(document.public_reference),
            "passport_id": str(document.passport_version.passport.public_reference),
            "version_number": document.passport_version.version_number,
            "status": document.status,
        }

    def get_passport(self, passport_id):
        try:
            reference = UUID(str(passport_id))
        except (TypeError, ValueError, AttributeError):
            return None
        passport = DigitalPassport.objects.select_related("latest_version").filter(
            public_reference=reference
        ).first()
        if passport is None or passport.latest_version_id is None:
            return None
        return {
            "passport_id": str(passport.public_reference),
            "latest_version_number": passport.latest_version.version_number,
        }
