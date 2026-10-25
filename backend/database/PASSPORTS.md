# Digital Passport foundation

The passports app stores one permanent `DigitalPassport` identity per student and
an append-only sequence of issued `PassportVersion` records. Passport, student,
credential public reference, and version public reference UUIDs remain separate.

## Snapshot structure

Each issued version stores the student profile required to reproduce that version.
`PassportVersionCredential` freezes the included credential's public reference,
issuer identity, issue date, and optional expiry. `PassportVersionSkill` freezes
the represented catalog fields. `PassportVersionCredentialSkill` preserves which
credential represented each skill. Source foreign keys remain protected, while
snapshot values do not change when a current student profile or skill changes.

Version status describes historical issuance. Current validity is evaluated when
building a new version: only `ISSUED` credentials issued by the effective time and
not revoked or expired at that time are included. Old versions remain issued
historical records even after their credentials cease to be current.

## Publication and idempotency

`publish_passport_version()` locks the student, permanent passport, and eligible
credential rows in a consistent order. It creates a draft, writes normalized
snapshot rows in bulk, seals the version, advances the latest pointer, and records
a `PassportUpdateEvent` in one short transaction. The unique passport/version
number and passport/event key constraints arbitrate competing workers. An exact
event replay returns its recorded version. A distinct event whose content is
unchanged records a new receipt and reuses the latest snapshot.

PostgreSQL triggers enforce student ownership, source snapshot fidelity, matching
credential-skill relationships, sequential latest pointers, valid credentials at
publication, and immutability of issued versions, snapshot rows, and update
receipts. Serialization failures and deadlocks have at most three retries when the
service is not nested in a caller-owned transaction.

## Credential lifecycle integration

After a credential transaction creates its immutable `CredentialLifecycleEvent`,
the orchestration layer must call:

```python
schedule_passport_update_for_credential_event(lifecycle_event_id=event.id)
```

The helper uses `transaction.on_commit()` and then calls
`publish_passport_for_credential_event()`, so passport publication never extends
the credential transaction. It is deliberately not called inside the existing
credential service until the owning modules agree on failure reporting and retry
delivery. The lifecycle event UUID is the durable passport idempotency key.

Credential expiry does not create a lifecycle event. A scheduled application job
must publish a validity refresh after an expiry boundary if the latest passport
must change without another credential event. No task queue is introduced here.

## PDF documents

`PassportDocument` records stored PDF artifacts separately from immutable
`PassportVersion` snapshots. A version may have multiple document generations
(for example after a renderer/template upgrade); each generation has its own
public UUID, renderer/request fingerprint, SHA-256, byte size, storage key, status,
timestamps, and failure information. An exact request replay reuses the issued
generation. Issued metadata is immutable and document rows cannot be deleted.

`generate_passport_document()` claims a short database-backed lease, commits,
then renders and writes storage outside all database transactions. Final metadata
is issued in a second short transaction only after storage succeeds. A failed
attempt remains visible and may be retried using the same document record. The
attempt UUID is part of the object key, preventing a stale worker from overwriting
a newer attempt. PostgreSQL constraints and triggers protect sequential
generation numbers, state transitions, storage paths, immutable hashes, and
issued-version ownership across multiple Django workers.

The renderer consumes only the selected historical version's snapshot rows; it
does not consult current Student, Skill, Achievement, or Credential state. It
reuses `templates/Passport_Blank.pdf` and the existing stamp assets, returns bytes
in memory, and appends credential pages as needed. The legacy
`pdf_generator.generate_passport()` Excel adapter remains available and now calls
the same renderer. No PDF endpoint is enabled by this foundation.

Django's storage API is the storage abstraction. Local development defaults to
private files below `MEDIA_ROOT`; a private object-store backend can replace it
without changing document rows. Keys are exact, generated server-side, and
validated as `passports/<passport UUID>/<version UUID>/<document UUID>/<attempt
UUID>.pdf`. `open_passport_document_for_student()` requires the owning internal
Student UUID and never accepts a caller-provided path. Public web serving from
`MEDIA_ROOT` must remain disabled.

The following settings are configurable, with conservative defaults:

- `PASSPORT_PDF_MAX_SKILLS=100`
- `PASSPORT_PDF_MAX_CREDENTIALS=100`
- `PASSPORT_PDF_MAX_BYTES=5242880` (5 MiB, matching verification upload policy)
- `PASSPORT_PDF_LEASE_SECONDS=120`
- `PASSPORT_PDF_WAIT_SECONDS=10`

The synchronous service is appropriate for bounded documents but deliberately
has no HTTP integration. A later request layer should enqueue generation when
latency measurements justify background work, preserve the same durable service
contract, and return document status instead of keeping a web request open.

`PassportDocumentRepository` adapts issued document hashes to the existing
verification service interface. It identifies authentic historical documents and
lets that service distinguish the latest version from an outdated one. No
verification module was modified.

Blockchain transactions and cryptographic proofs can later reference the
document or version from separate append-only models. Core passport and PDF
issuance do not depend on blockchain confirmation.

Tests use `config.foundation_test_settings`, which accepts only loopback PostgreSQL
and never reads the shared Neon connection. The reference `schema.sql` is not used.
