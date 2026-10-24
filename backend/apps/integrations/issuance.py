
class CredentialIssuerNotConfigured(Exception):
    pass


def issue_credential(
    student_id,
    course_id,
    source_event_id,
):
    """
    Placeholder for Developer 1's issuance service.

    The real implementation must be connected
    before actual synchronization is enabled.
    """

    raise CredentialIssuerNotConfigured(
        "Credential issuance service is not connected."
    )
