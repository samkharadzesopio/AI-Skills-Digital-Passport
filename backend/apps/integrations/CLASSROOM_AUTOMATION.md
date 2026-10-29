# Classroom completion automation and durable replay

This document describes the completion pipeline and its operational boundaries.
Credential-to-Passport lifecycle processing uses the existing durable refresh outbox.

## Scope and trust

`ClassroomCredentialAutomation` consumes the existing **simulated**, server-owned
`ClassroomService` adapter. This does not connect to or attest evidence from the
real BTU API. Institutional course approval is represented by the checked-in
`mock_data/approved_ai_courses.json` catalog: an exact course ID, enabled flag
(default true), passing threshold, and explicit skill-code list. Duplicate course
IDs, missing/duplicate/unknown skills, disabled courses, malformed dates, unknown
students, and failed/incomplete completions fail closed. No Student or issuer is
created. Routine eligible events need no individual approval.

The API accepts only the `dry_run` control. No caller-provided events, issuer,
source identity, Student UUIDs, or mappings are accepted. Shared URLs and explicit
`accounts.sync_classroom` permission already existed and are preserved. Session
CSRF protection remains enabled. Preview defaults to true, is read-only, and
validates Student, mapping, and issuer configuration; it is not a reservation or
a guarantee against later configuration changes.

## Configuration and migration review

Classroom and credential issuance use the fixed institutional reference
`BTU-UNIVERSITY`. `config.settings` rejects any different
`BTU_CLASSROOM_ISSUER_REFERENCE`, and the request API never accepts an issuer value.
An authorized administrator must provision the trusted issuer record using
`manage.py provision_btu_issuer`; automation does not create or trust it implicitly.
Public verification also requires an explicit allowlist match and a database issuer
record marked trusted.

The sample environment binding is:

```python
BTU_CLASSROOM_ISSUER_REFERENCE = os.environ.get(
    'BTU_CLASSROOM_ISSUER_REFERENCE', 'BTU-UNIVERSITY'
)
```

Never accept the issuer reference from HTTP data or auto-provision the trusted row.

`integrations/0001_initial` adds only `ClassroomSyncEvent`. Dependencies:
`skills/0002_verified_achievements`, `credentials/0004_seal_credential_contents`,
and the swappable `AUTH_USER_MODEL` initial migration. It references existing
AchievementSourceEvent (and thus its achievements), Credential and User records;
it does not duplicate any domain model. `integrations/0002` adds ImportRun and
expands the source constraint. The combined graph was applied on a disposable local
PostgreSQL 18.6 database; no Neon migration was run.

## Transactions, duplicates, recovery

1. Fetch the trusted source batch outside database transactions (maximum 5,000
   events; no throughput claim). Register each bounded JSON payload in the inbox
   under a unique `(BTU_CLASSROOM, source_event_id)` key and SHA-256 fingerprint.
   Conflicting event reuse is rejected without replacing the original payload.
2. Lock the inbox row, validate current approved mapping/issuer, and invoke
   `award_classroom_skills` -> `record_verified_achievements`. Commit achievements,
   frozen mapping/issuer, and the source receipt link together. PROCESSING is a
   transactional transition; a crash rolls it back, so no stuck lease is needed.
3. Lock the same inbox row again, revalidate its frozen configuration, replay the
   achievement service for the same UUIDs, and call the existing `issue_credential`.
   Commit the returned credential link and CREDENTIAL_ISSUED state in that same
   transaction. An issuance failure rolls back only this second stage. First-stage
   achievements remain durably referenced and are reused on replay.

The credential key is `classroom:v1:` plus SHA-256 of the trusted source/event
identity. Issuance always omits `issued_at`; retries do not introduce a new timestamp
into the request fingerprint. A successful inbox replay skips without reissuing.
An old achievement receipt created before the inbox existed is also recoverable.
Concurrent workers serialize through PostgreSQL row locks and existing domain
uniqueness guarantees. Live processing rejects caller-owned outer transactions;
do not enable ATOMIC_REQUESTS for these processing views without explicit handling.

Failures store an error classification, attempt count, retryability and next retry
time, not raw exception strings. Five processing attempts are allowed, with delayed
exponential retry (60, 120, 240, 480 seconds); no sleeping under locks. Automatic
replay respects the deadline. Authorized explicit retry can bypass the delay and
retry a repaired validation/configuration failure but cannot bypass the five-attempt
budget. Exhausted events remain visible for operator review; there is no public
budget-reset or payload-edit interface. Provision/repair the cause before retrying.
If PostgreSQL itself is unavailable, storing failure metadata cannot be guaranteed;
the source must remain replayable and operators must rerun ingestion after recovery.

A changed mapping or issuer blocks incomplete events instead of silently changing
already recorded awards. Completed events stay completed after catalog changes;
corrections/revocations use Developer 1's lifecycle, never rewriting history.
Unchanged payload replay only is permitted. Semantic duplicate completions carrying
different upstream event IDs are a source-contract issue, not automatically merged.

## APIs and scheduled operation

Existing mount: `/api/integrations/`.

- POST `classroom/sync/`: `{ "dry_run": true }` preview (default), or false to persist.
  Returns processed/issued/skipped/failed/would_issue counts, eligible preview fields,
  sanitized failures and explicit `SIMULATED_BTU_CLASSROOM` provenance. Rejected
  incomplete/unapproved events count as failed, not issued. Counts are per input event.
- GET `classroom/events/`: cursor-paginated history, 50 records/page, no raw payload.
- POST `classroom/events/<inbox UUID>/retry/`: retry stored event; accepts no replacement data.

All require the existing explicit admin sync permission. The first triggering
administrator is retained on the inbox. Non-preview administrative actions are
recorded by the shared security-audit middleware. Public verification is handled by
the separate PostgreSQL-backed verification service.

Trusted operator commands, from backend, use the same pipeline:

```sh
python manage.py sync_classroom                 # preview only
python manage.py sync_classroom --apply         # ingest and issue
python manage.py retry_classroom_events         # up to 100 pending/due events
```

Run retry polling from an authorized scheduler (e.g. every minute); no scheduler
is installed or deployed by this commit. Pending events survive restarts. Mapping
failures and exhausted retries need deliberate operator remediation. The service
uses no in-memory authoritative ledger. Legacy achievement-only/in-memory demo
sync classes remain for compatibility but are not used by the live API.

## Credential-to-Passport lifecycle

The existing `issue_credential` and `revoke_credential` services persist durable
Passport refresh records with their lifecycle events. `run_backend_workers` polls
pending Classroom, import, and Passport refresh work in bounded batches; it also
scans for credential expirations every minute. Refresh workers publish from current
credential state, preserve prior versions, and do not generate PDFs in the database
transaction. Do not add a second publishing path inside integrations.

The worker is code only until deployed under a supervised process. A committed
credential does not mean the asynchronous Passport refresh or PDF generation has
completed; monitor their durable states and retries.

## Validation

Python 3.13.13, Django 6.1.2, isolated PostgreSQL 18.6 at 127.0.0.1:55435.
Synthetic records and issuer only. Test settings never load `.env` or
`DATABASE_URL`; Django creates and drops a uniquely named disposable test database.

```sh
cd /workspace/AI-Skills-Digital-Passport/backend
../.venv-auth/bin/python manage.py test apps.integrations apps.skills apps.credentials apps.passports apps.students apps.accounts apps.verification --settings=apps.integrations.postgres_test_settings
../.venv-auth/bin/python manage.py makemigrations --check --dry-run --settings=apps.integrations.postgres_test_settings
```

The inherited foundation runner explicitly excludes two legacy schema.sql
comparison tests; it does not disable assertions or concurrency tests. The combined
suite includes an end-to-end Classroom-to-PDF verification test and a 5,000-student
indexed lookup test. Neither establishes production request capacity. The test
harness accepts both Active and ACTIVE synthetic status spellings; no runtime
eligibility policy was changed.
