
import hashlib

from .document_repository import MockDocumentRepository


MAX_PDF_SIZE = 5 * 1024 * 1024  # 5 MB


class DocumentVerificationService:
    def __init__(self, repository=None):
        self.repository = (
            repository
            if repository is not None
            else MockDocumentRepository()
        )

    def verify(self, uploaded_file):
        if uploaded_file is None:
            return self._result(
                "INVALID", "No PDF file supplied."
            )

        if uploaded_file.size > MAX_PDF_SIZE:
            return self._result(
                "INVALID", "PDF exceeds the 5 MB limit."
            )

        if (
            uploaded_file.content_type
            != "application/pdf"
        ):
            return self._result(
                "INVALID", "Expected a PDF upload."
            )

        pdf_bytes = uploaded_file.read(
            MAX_PDF_SIZE + 1
        )

        if len(pdf_bytes) > MAX_PDF_SIZE:
            return self._result(
                "INVALID", "PDF exceeds the 5 MB limit."
            )

        if not pdf_bytes.startswith(b"%PDF-"):
            return self._result(
                "INVALID", "Invalid PDF header."
            )

        if b"%%EOF" not in pdf_bytes[-1024:]:
            return self._result(
                "INVALID", "PDF end marker is missing."
            )

        pdf_hash = hashlib.sha256(
            pdf_bytes
        ).hexdigest()

        document = self.repository.find_by_hash(
            pdf_hash
        )

        if document is None:
            return self._result(
                "UNVERIFIABLE",
                "No matching issued document was found."
            )

        if document.get("status") == "REVOKED":
            return self._result(
                "INVALID",
                "This document has been revoked."
            )

        if document.get("status") != "ISSUED":
            return self._result(
                "UNVERIFIABLE",
                "Document issuance is not confirmed."
            )

        passport = self.repository.get_passport(
            document["passport_id"]
        )

        if passport is None:
            return self._result(
                "UNVERIFIABLE",
                "Passport version data is unavailable."
            )

        version = document.get("version_number")
        latest = passport.get("latest_version_number")

        if (
            type(version) is not int
            or type(latest) is not int
            or version < 1
            or latest < 1
            or version > latest
        ):
            return self._result(
                "UNVERIFIABLE",
                "Passport version data is inconsistent."
            )

        if version < latest:
            return self._result(
                "OUTDATED",
                "Authentic PDF, but a newer issued "
                "passport version exists.",
                authentic=True,
                version=version,
                latest_version=latest,
            )

        return self._result(
            "VALID",
            "Authentic and latest issued "
            "Digital Passport.",
            authentic=True,
            version=version,
            latest_version=latest,
        )

    @staticmethod
    def _result(
        status,
        message,
        authentic=False,
        version=None,
        latest_version=None,
    ):
        return {
            "status": status,
            "authentic": authentic,
            "is_latest": (
                status == "VALID"
                if authentic else None
            ),
            "passport_version": version,
            "latest_version": latest_version,
            "message": message,
            "source": "SIMULATED_DOCUMENT_REGISTRY",
        }
