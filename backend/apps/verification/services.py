
from datetime import datetime, timezone

from .repositories import PostgreSQLCredentialRepository


class CredentialVerificationService:
    def __init__(self, repository=None, clock=None):
        self.repository = (
            repository if repository is not None
            else PostgreSQLCredentialRepository()
        )
        self.clock = clock or (
            lambda: datetime.now(timezone.utc)
        )

    def verify(self, credential_id):
        record = self.repository.get_by_id(credential_id)
        return self.verify_record(record, credential_id)

    def verify_record(self, record, credential_id=None):
        """Evaluate an already-fetched record without additional database lookups."""
        if record is None:
            return self._result(credential_id, "NOT_FOUND")

        if record.get("issuer_trusted") is not True:
            return self._result(credential_id, "INVALID")

        native = record.get('_credential')
        if native is not None:
            return self._result(credential_id, native.verification_status_at(self.clock()))

        if record.get("status") == "REVOKED":
            return self._result(credential_id, "REVOKED")

        if record.get("status") != "ISSUED":
            return self._result(credential_id, "INVALID")

        try:
            issued_at = self._parse_date(
                record["issued_at"]
            )
            expires_at = self._parse_date(
                record.get("expires_at")
            )
        except (KeyError, ValueError, TypeError):
            return self._result(credential_id, "INVALID")

        now = self.clock()

        if issued_at is None or issued_at > now:
            return self._result(credential_id, "INVALID")

        if expires_at is not None:
            if expires_at < issued_at:
                return self._result(credential_id, "INVALID")

            if now >= expires_at:
                return self._result(credential_id, "EXPIRED")

        return self._result(credential_id, "VALID")

    @staticmethod
    def _parse_date(value):
        if value is None:
            return None

        if not isinstance(value, str):
            raise TypeError("Expected a date string")

        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            raise ValueError("Timezone required")

        return parsed

    def _result(self, credential_id, status):
        return {
            "credential_id": credential_id,
            "status": status,
            "verified": status == "VALID",
            "source": getattr(self.repository, "source", "SIMULATED_CREDENTIAL_REGISTRY"),
        }
