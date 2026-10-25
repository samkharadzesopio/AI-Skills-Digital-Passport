# Phase B: Classroom automation and durable replay

Branch: `feature/dev2-automation-verification`, based on integration `c64d4a2`.
Only integrations files change. Verification/security phases are separate sessions.

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

Developer 1 must provision and approve a real `CredentialIssuer.reference`.
There is intentionally no approved reference guessed here. The Django setting
`BTU_CLASSROOM_ISSUER_REFERENCE` must equal that existing reference. Missing
configuration or an absent row produces a durable retryable failure without awards.

Proposed shared-settings addition (NOT applied by this phase):

```python
BTU_CLASSROOM_ISSUER_REFERENCE = os.environ.get('BTU_CLASSROOM_ISSUER_REFERENCE', '')
```

Setting an environment variable alone will not affect Django until that binding
is integrated. Never accept the reference from HTTP data or auto-provision it.

`integrations/0001_initial` adds only `ClassroomSyncEvent`. Dependencies:
`skills/0002_verified_achievements`, `credentials/0004_seal_credential_contents`,
and the swappable `AUTH_USER_MODEL` initial migration. It references existing
AchievementSourceEvent (and thus its achievements), Credential and User records;
it does not duplicate any domain model. Review this graph with Developer 1 before
shared migration. Only disposable local PostgreSQL was migrated during testing.

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
administrator is retained on the inbox. A full per-action security audit timeline
and public verification hardening remain Phase D work.

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

## Developer 1 lifecycle contract (still pending)

This code calls only `issue_credential`, which creates CredentialLifecycleEvent.
It never calls Passport publishing or schedules another Passport hook. Developer 1
owns attaching reliable Passport processing to committed lifecycle events, including
revocation, retry delivery, expiry refresh and out-of-order event handling. A
committed credential is NOT a claim that Passport/PDF publication completed.
Do not add a second publishing path inside integrations.

## Validation

Python 3.13.5, Django 6.1.2, isolated PostgreSQL 17 at 127.0.0.1:55432. Synthetic
records and issuer only. Test settings never load `.env` or DATABASE_URL. The DB
role is the current OS user; create an empty local `classroom_tests` database first.

```sh
cd /workspace/AI-Skills-Digital-Passport/backend
../.venv-auth/bin/python manage.py test apps.integrations apps.skills apps.credentials apps.passports apps.students apps.accounts apps.verification --settings=apps.integrations.postgres_test_settings
../.venv-auth/bin/python manage.py makemigrations --check --dry-run --settings=apps.integrations.postgres_test_settings
```

The inherited foundation runner explicitly excludes the two legacy schema.sql
comparison tests; it does not disable assertions or concurrency tests. The new
harness accepts both Active and ACTIVE synthetic status spellings like the existing
auth harness; no runtime eligibility policy was changed. There are no verification
load/performance claims in Phase B. Test results and the commit are reported in chat.
