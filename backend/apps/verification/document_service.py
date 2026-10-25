
import hashlib

from apps.passports.document_repository import PassportDocumentRepository


MAX_PDF_SIZE = 5 * 1024 * 1024  # 5 MB


class DocumentVerificationService:
    def __init__(self, repository=None):
        self.repository = (
            repository
            if repository is not None
            else PassportDocumentRepository()
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

        # Bound actual bytes independently of the client-supplied size. Do not
        # invoke a PDF renderer/parser on arbitrary public uploads.
        hasher = hashlib.sha256()
        total = 0
        header = b''
        tail = b''
        while True:
            chunk = uploaded_file.read(min(65536, MAX_PDF_SIZE + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_PDF_SIZE:
                return self._result('INVALID', 'PDF exceeds the 5 MB limit.')
            hasher.update(chunk)
            if len(header) < 8:
                header = (header + chunk)[:8]
            tail = (tail + chunk)[-1024:]
        if not header.startswith(b'%PDF-'):
            return self._result('INVALID', 'Invalid PDF header.')
        if b'%%EOF' not in tail:
            return self._result('INVALID', 'PDF end marker is missing.')
        pdf_hash = hasher.hexdigest()

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

        if isinstance(self.repository, PassportDocumentRepository):
            from .passport_service import PassportVerificationService
            current = PassportVerificationService().verify(document['passport_id'], number=document["version_number"])
            status = current['status']
            if status == 'NOT_FOUND':
                status = 'UNVERIFIABLE'
            result = self._result(status, 'Registered document integrity and current credential status checked.',
                                  authentic=True, version=current["passport_version"], latest_version=current["latest_version"])
            result.update(credential_status=current['credential_status'], credential_counts=current['credential_counts'])
            # Version currency and credential validity are independent facts.
            result['is_latest'] = current['is_latest']
            return result

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
            return self._result('OUTDATED', 'Authentic PDF, but a newer issued passport version exists.',
                                authentic=True, version=version, latest_version=latest)
        return self._result('VALID', 'Registered PDF matches the latest issued passport version.',
                            authentic=True, version=version, latest_version=latest)

    def _result(
        self, status,
        message,
        authentic=False,
        version=None,
        latest_version=None,
    ):
        return {
            "status": status,
            "credential_status": "UNVERIFIABLE",
            "credential_counts": {},
            "authentic": authentic,
            "is_latest": (
                status == "VALID"
                if authentic else None
            ),
            "passport_version": version,
            "latest_version": latest_version,
            "message": message,
            "source": "POSTGRESQL_DOCUMENT_REGISTRY" if isinstance(self.repository, PassportDocumentRepository) else "SIMULATED_DOCUMENT_REGISTRY",
        }
