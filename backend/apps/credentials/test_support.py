"""Small, isolated helpers for creating trusted issuers in PostgreSQL tests."""

import uuid


class SyntheticCredentialAdmin:
    is_authenticated = True
    is_active = True
    is_email_verified = True
    role = "ADMIN"
    is_staff = True
    is_superuser = False
    email = "credential-admin@btu.edu.ge"

    def __init__(self):
        self.pk = uuid.uuid4()

    def has_perm(self, permission):
        return permission == "accounts.manage_credentials"


def create_test_issuer(display_name):
    from .services import provision_btu_issuer

    return provision_btu_issuer(
        actor=SyntheticCredentialAdmin(),
        display_name=display_name,
    )[0]
