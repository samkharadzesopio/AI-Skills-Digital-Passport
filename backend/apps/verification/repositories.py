
import json
from pathlib import Path


class MockCredentialRepository:
    def __init__(self, data_path=None):
        self.data_path = (
            Path(data_path)
            if data_path is not None
            else Path(__file__).resolve().parent
            / "mock_data"
            / "credentials.json"
        )

    def get_by_id(self, credential_id):
        with self.data_path.open(
            "r", encoding="utf-8"
        ) as file:
            records = json.load(file)

        for record in records:
            if record["credential_id"] == credential_id:
                return record

        return None


class PostgreSQLCredentialRepository:
    source = 'POSTGRESQL_CREDENTIAL_REGISTRY'

    def get_by_id(self, credential_id):
        from uuid import UUID
        from django.conf import settings
        from apps.credentials.models import Credential
        try:
            reference = UUID(str(credential_id))
        except (TypeError, ValueError, AttributeError):
            return None
        from .records import trusted_issuer
        row = Credential.objects.filter(public_reference=reference).values(
            'status', 'issued_at', 'expires_at', 'issuer_reference',
            'issuer__reference', 'issuer__is_trusted',
        ).first()
        if row is None:
            return None
        # Reuse the domain method on a detached projection; never save it.
        native = Credential(status=row['status'], issued_at=row['issued_at'], expires_at=row['expires_at'])
        return {'_credential': native, 'status': row['status'],
                'issued_at': row['issued_at'].isoformat(),
                'expires_at': row['expires_at'].isoformat() if row['expires_at'] else None,
                'issuer_trusted': trusted_issuer(
            row['issuer_reference'], row['issuer__reference'], row['issuer__is_trusted'])}
