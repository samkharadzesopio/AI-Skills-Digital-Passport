"""Private adapter data, never serialized directly into a public response."""
from django.conf import settings


def trusted_issuer(reference, current_reference, is_trusted):
    approved = getattr(settings, 'VERIFICATION_TRUSTED_ISSUER_REFERENCES', ())
    return bool(isinstance(approved, (list, tuple)) and approved and
                reference == current_reference and reference in approved and is_trusted is True)


def credential_record(credential):
    return {'_credential': credential, 'issuer_trusted': trusted_issuer(
        credential.issuer_reference, credential.issuer.reference, credential.issuer.is_trusted)}
