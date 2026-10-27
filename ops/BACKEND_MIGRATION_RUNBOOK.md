# Backend lifecycle deployment and forward recovery

This is an operator plan. This integration task authorizes disposable rehearsals
only. It does not authorize applying migrations to Neon or persistent local data.
Public Amoy deployment and transactions remain pending separate authorization.

## Schema delta

The pre-blockchain integration leaves are accounts `0006_deferredmail_securityaudit`
and passports `0006_snapshot_subcategory`. The added migrations are:

| Migration | Dependencies and effect |
| --- | --- |
| accounts/0007_alter_user_options | accounts/0006; defines two explicit lifecycle permissions; grants no user or group new privileges |
| passports/0007_passportlifecycleevent_passportpublication_and_more | passports/0006, students/0002, swappable User; retains Student FK while replacing one-to-one uniqueness with an ACTIVE-only unique index; adds lifecycle events, PDF queue and identity fields |
| passports/0008_lifecycle_integrity | passports/0007 and accounts/0007; backfills frozen first-issued names/date and independent salts; installs identity/permission/audit guards |
| blockchain/0001_initial | passports/0008 and credentials/0005_credentialissuerprovisioningevent_and_more; creates proof operations, observations and signer nonce reservations |
| blockchain/0002_proof_integrity | blockchain/0001 and passports/0008; protects signed payloads, proof bindings and monotonically increasing nonce reservations |

Existing migration files are retained. No Student, credential, version or PDF
table is dropped by the forward migration. Historical permanent Passport IDs,
public references and version IDs remain separate and retain their values.

## Preflight and backup

1. Pin the reviewed application commit and dependency lock versions. Verify the
   actual target schema with `showmigrations --plan` and `migrate --plan` using
   the intended deployment settings. Review `sqlmigrate` output for all five
   migrations. Never use disposable test settings on persistent data.
2. Rehearse a restored, access-controlled backup in staging. Use synthetic data
   for shareable reports. Measure table sizes, index build duration, lock waits,
   available disk/WAL space and migration duration on representative volume.
3. Take a verified PostgreSQL custom-format backup and an immutable copy of
   media/PDF storage, with a manifest of document IDs, storage keys, byte sizes
   and SHA-256 hashes. Prove restoration before proceeding. Keep database and
   media backup access restricted. Record the backup's application/schema commit.
4. Inventory Student IDs/external IDs, linked account IDs/grants, Passport IDs
   and references, version IDs/numbers/snapshot hashes, credential links and PDF
   references/hashes. Check that each pre-upgrade Student has at most one
   Passport and there are no orphaned references.
5. Schedule maintenance. Stop incoming writes, imports, OTP/mail processing,
   Classroom retries, credential refreshes, PDF publication and blockchain
   workers. Drain or record outstanding jobs. Stop old web processes too: old
   code assumes a one-to-one Passport relation and cannot safely run concurrently
   with the historical identity schema. Retain signer exclusive ownership.

## Locking and cost

`0007` changes constraints and adds columns/tables/indexes; PostgreSQL DDL takes
table locks, and ACTIVE uniqueness validation scans existing rows. Do not assume
online or constant-time deployment. Schema-editor transactional DDL protects a
failed individual migration but does not combine all migrations into one unit.

`0008` visits all Passports in chunks of 500, queries each first issued version,
and updates every identity. It therefore performs work proportional to Passport
count, plus per-identity version lookup and WAL generation. The transaction can
retain row locks until completion. Chunked iteration limits Python memory; it
does not commit each chunk. Shared-data duration has not been established by a
small disposable rehearsal. Set operator-reviewed lock/statement timeouts and
maintenance duration after staging measurements; avoid endless automatic retry.

The first issued frozen snapshot supplies legal names, even if the current
Student record differs. Identities without issued versions receive current
Student names and retain a null first-issued date. Each receives a fresh salt.

## Apply and verify

1. With old processes stopped and backups verified, apply the reviewed forward
   plan once using the pinned code and explicit deployment settings. Record
   migration output and timings without connection strings or signer details.
2. If interrupted, keep maintenance mode active. Inspect `django_migrations`
   and the database; resume the forward plan only after identifying the last
   committed migration. Atomic migration rollback covers its own transaction;
   an earlier completed migration remains applied. Do not start mixed old/new
   application processes between `0007` and `0008`.
3. Compare every preflight invariant and count. Verify unchanged identifiers,
   snapshot/PDF hashes and credential ownership; frozen name/date backfill;
   one ACTIVE identity per Student; permission grants unchanged; installed
   immutability/lifecycle/nonce triggers; no migration drift. Retrieve sample
   historical PDFs and recompute their hashes. Retain evidence privately.
4. Grant `manage_legal_identity` and `manage_passport_lifecycle` only to approved
   operators through existing explicit provisioning. A role flag grants neither.
5. Start updated web processes, then `run_backend_workers`. This worker handles
   auth mail, integration recovery, credential refreshes, PDF publication and
   bounded retention. It deliberately does not ingest simulated Classroom data
   automatically and does not hold the institutional signing key.
6. Start `process_blockchain_proofs --watch` in a separate, exclusively operated
   signer process only after its target, trusted BTU issuer, registry runtime,
   network, role and key-file permissions are verified. With public deployment
   still pending, retain disabled blockchain configuration and fail-closed
   UNVERIFIABLE responses; do not label registry-only evidence chain verified.
7. Review queues, retry bounds, errors and latency before reopening writes.
   Verify OTP/session/CSRF, own-record access, public privacy, current versus
   historical identity selection and PDF retrieval. Perform any public-network
   acceptance only under a later explicit deployment authorization.

## Recovery restrictions

Once cancelled identities or proof/lifecycle history exist, downgrades are
deliberately refused. Never remove triggers, delete historical identities,
discard proofs, edit issued snapshots/PDFs or reset nonce counters to force a
rollback. Prefer a reviewed forward fix with the preserved backup available.
Restoring a backup requires a separate maintenance/recovery decision and must
account for any transactions broadcast since that backup.

For a stuck operation, inspect with `inspect_blockchain_operation UUID
--check-chain`. Reviewed original-byte rebroadcast uses
`recover_blockchain_operation UUID --expected-transaction-hash REVIEWED_HASH
--rebroadcast`. It preserves signature/hash/nonce and refuses unsafe competing
nonce or fee conditions. There is no automatic fee-bump/replacement system;
irrecoverably underpriced or externally consumed nonces require a separately
reviewed forward recovery design. Never send unrelated transactions from the
institutional issuer or reuse its key across competing workers/services.
