# Credential management foundation

This app stores issued credentials over verified-achievement records. A credential has a private database UUID and a distinct public verification UUID. Student external university IDs are not used as credential or foreign-key identifiers.

## Data and integrity

- `CredentialIssuer` has one fixed trusted identity, `BTU-UNIVERSITY`. Provision it with `manage.py provision_btu_issuer --actor-email <admin-email>`. The named active, verified staff administrator must hold `accounts.manage_credentials`; optional `--display-name` changes are audited. The database prevents trusted issuer identity changes and keeps the provisioning audit append-only. There is no public issuer-registration endpoint.
- `Credential` belongs to one student and one registered issuer. It snapshots issuer reference/name and stores the request fingerprint, issue/optional expiry times, status, and revocation data.
- `CredentialAchievement` links one credential to one or more verified achievements. Multiple achievements may be included, but all must be verified and belong to the same student. Database triggers enforce this at insert time and seal the contents after the issued event.
- `CredentialLifecycleEvent` is append-only and has at most one issue and one revoke event. PostgreSQL triggers require audit records to agree with credential state. Credential rows cannot be deleted or have issuance facts rewritten. Revocation is the only permitted state transition.

## Service contract

Use `apps.credentials.services.issue_credential` inside the trusted integration service. The request accepts the fixed issuer reference `BTU-UNIVERSITY`, a stable idempotency key, verified Achievement UUIDs, and optional timezone-aware expiry/issue dates. The configurable `CREDENTIAL_MAX_ACHIEVEMENTS` defaults to 256. Idempotency key and issuer reference are capped at 255 characters; revocation reason is capped at 2,000 characters. Exact retries return the same row; changed payload on the same issuer/key raises `IdempotencyConflict`. Reusing a key for a logically different request is rejected. A different key may issue another credential over the same achievement set.

Issuance validates request shape and fingerprints before transaction start, then locks the achievement rows in UUID order, validates DB-backed state, and writes credential, links, lifecycle event, and durable Passport refresh request atomically. Unique constraints arbitrate cross-worker idempotency races. Serialization failures and deadlocks have at most three retries when not nested in a caller-owned transaction. The service fails closed if the trusted BTU issuer has not been provisioned.

`revoke_credential` uses the existing Accounts policy through `CREDENTIAL_REVOCATION_AUTHORIZER`. The policy receives the authenticated principal and credential and requires the existing `accounts.revoke_credentials` administrator permission. Passing an actor ID alone does not authorize revocation. The revoke event and durable Passport refresh request commit atomically; the policy performs no network lookup inside the transaction.

## Passport refresh processing

`CredentialPassportRefresh` is a PostgreSQL transactional outbox. A durable refresh request is created in the same transaction as each issue/revoke lifecycle event. A robust `on_commit` callback attempts immediate processing; pending database rows remain the delivery source of truth if the process stops or publication fails. The worker leases bounded batches with `SELECT ... FOR UPDATE SKIP LOCKED`, performs Passport publication after releasing outbox locks, and completes the row only if its lease token still matches. Failed work is retried with bounded exponential backoff and becomes terminal after the configured attempt limit; operators may explicitly requeue failed work.

Run `manage.py process_passport_refreshes --batch-size 100` from a scheduled process. Run `manage.py process_passport_refreshes --retry-failed` only when operators intend to retry terminal failures. Settings: `PASSPORT_REFRESH_LEASE_SECONDS` (120), `PASSPORT_REFRESH_MAX_ATTEMPTS` (8), and `PASSPORT_REFRESH_RETRY_BASE_SECONDS` (5). Stale processing leases are reclaimable. The worker has bounded batch and retry limits and makes no PDF, email, blockchain, or network calls.

`manage.py refresh_expired_credentials --batch-size 100` is suitable for periodic scheduling. It scans the partial index for expired issued credentials that are still present in the latest Passport snapshot, groups by student/expiry boundary, and inserts idempotent outbox events. Credential verification evaluates expiry directly and does not wait for this Passport snapshot refresh.

## Integration status

The existing verification service is still backed by mock records. `Credential.verification_status_at()` maps database state to its status vocabulary (`VALID`, `REVOKED`, `EXPIRED`, `INVALID`), while `NOT_FOUND` remains a lookup result. A verifier repository/adapter must look up the public UUID and supply an issuer-trust decision before credentials become verifiable through the existing endpoint. No credential verification endpoint or live Classroom sync implementation is included here; Passport refresh is implemented through the service/outbox described below.

## Developer 2 integration contract

Classroom orchestration should call the existing `issue_credential()` service with issuer reference `BTU-UNIVERSITY`, a deterministic idempotency key derived from the upstream completion/source event, and the UUIDs of the verified achievements to credential. It returns the existing `Credential` instance. Exact retries return that row; payload conflicts raise `IdempotencyConflict`; malformed, unknown, cross-student, or unverified achievements raise `ValidationError`; a missing trusted BTU issuer raises `ImproperlyConfigured`. The service itself writes lifecycle and Passport refresh events. The current `apps/integrations/issuance.py` remains a not-configured placeholder, so Developer 2 must map approved Classroom course completions into verified achievements and invoke this contract before live synchronization can operate.

## Migration/testing

Migrations add the core tables, foreign keys, indexes, constraints, and PostgreSQL integrity triggers. Apply only through Django migrations. Isolated tests use `config.foundation_test_settings`, which requires loopback PostgreSQL and never reads Neon `.env` configuration.
