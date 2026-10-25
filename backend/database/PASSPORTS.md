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

## Future documents and blockchain proofs

PDF artifacts can later reference `PassportVersion` from a separate document
model containing storage location, SHA-256, generation time, and document status.
Blockchain transactions and cryptographic proofs can likewise reference the
document or version from separate append-only models. Core passport issuance does
not depend on PDF generation or blockchain confirmation.

Tests use `config.foundation_test_settings`, which accepts only loopback PostgreSQL
and never reads the shared Neon connection. The reference `schema.sql` is not used.
