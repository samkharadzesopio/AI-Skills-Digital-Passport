# Credential management foundation

This app stores issued credentials over verified-achievement records. A credential has a private database UUID and a distinct public verification UUID. Student external university IDs are not used as credential or foreign-key identifiers.

## Data and integrity

- `CredentialIssuer` is provisioned through a trusted backend/operator process; no issuer registration endpoint is introduced.
- `Credential` belongs to one student and one registered issuer. It snapshots issuer reference/name and stores the request fingerprint, issue/optional expiry times, status, and revocation data.
- `CredentialAchievement` links one credential to one or more verified achievements. Multiple achievements may be included, but all must be verified and belong to the same student. Database triggers enforce this at insert time and seal the contents after the issued event.
- `CredentialLifecycleEvent` is append-only and has at most one issue and one revoke event. PostgreSQL triggers require audit records to agree with credential state. Credential rows cannot be deleted or have issuance facts rewritten. Revocation is the only permitted state transition.

## Service contract

Use `apps.credentials.services.issue_credential` inside the trusted integration service. The request accepts issuer reference, a stable idempotency key, achievement UUIDs, and optional timezone-aware expiry/issue dates. The configurable `CREDENTIAL_MAX_ACHIEVEMENTS` defaults to 256. Idempotency key and issuer reference are capped at 255 characters; revocation reason is capped at 2,000 characters. Exact retries return the same row; changed payload on the same issuer/key raises `IdempotencyConflict`. Reusing a key for a logically different request is rejected. A different key may issue another credential over the same achievement set.

Issuance validates request shape and fingerprints before transaction start, then locks the achievement rows in UUID order, validates DB-backed state, and writes credential, links, and audit event atomically. Unique constraints arbitrate cross-worker idempotency races. Serialization failures and deadlocks have at most three retries when not nested in a caller-owned transaction.

`revoke_credential` requires a configured local policy through `CREDENTIAL_REVOCATION_AUTHORIZER`. The policy receives the authenticated principal and credential and must return a trusted stable actor reference or reject. Passing an actor ID alone does not authorize revocation. Revocation is disabled when no policy exists. Configure authorization only after the Accounts team provides its principal and role contract; do not use a network lookup inside the policy or transaction.

## Integration status

The existing verification service is still backed by mock records. `Credential.verification_status_at()` maps database state to its status vocabulary (`VALID`, `REVOKED`, `EXPIRED`, `INVALID`), while `NOT_FOUND` remains a lookup result. A verifier repository/adapter must look up the public UUID and supply an issuer-trust decision before credentials become verifiable through the existing endpoint. Issuer registration must also be provisioned through the future trusted issuer/account workflow. No authentication, API endpoint, credential document, passport, blockchain, or Classroom sync implementation is included here.

## Migration/testing

Migrations add the core tables, foreign keys, indexes, constraints, and PostgreSQL integrity triggers. Apply only through Django migrations. Isolated tests use `config.foundation_test_settings`, which requires loopback PostgreSQL and never reads Neon `.env` configuration.
