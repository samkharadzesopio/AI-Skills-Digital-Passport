# Public verification integration review

Baseline: shared integration f8057c5. Work branch: feature/public-verification-integration.
The baseline already contains trusted issuer provisioning, credential lifecycle
outbox/retry/expiry, immutable Passport snapshots, PDF persistence, persistent OTP,
protected imports and their durable inbox. These were inspected and reused.
No competing lifecycle service or model was introduced.

## Gaps resolved

1. There was no public Passport-reference endpoint, only credential references and
   PDF uploads. Permanent and version reference endpoints now read existing UUIDs.
2. PDF status previously described integrity/latest only; a revoked credential in
   an authentic historical PDF could still produce a positive result. Verification
   now evaluates the exact snapshot's credentials against current authoritative
   Credential and issuer rows even when the refresh outbox is pending.
3. Credential validity checks now reuse Credential.verification_status_at for real
   database records. The existing injected mock adapter remains a test seam only.
4. Public reads avoid profile/storage fields; the existing document repository now
   selects only the fields its public contract needs. No verification path opens a
   filename or generates/reissues a PDF.
5. Verification rejections log scope and HTTP status only, never references,
   filenames, private data, raw addresses, codes, bodies or provider exceptions.
6. The shared test runner's required loopback variables are supplied by the existing
   ops/test_backend.sh helper, so it reproduces the actual combined harness.

## Public API

Existing endpoints remain:
- GET /api/verification/<credential-public-reference>/
- POST /api/verification/document/ (multipart file)

New endpoints:
- GET /api/verification/passport/<passport-public-reference>/ : latest issued snapshot
- GET /api/verification/passport-version/<version-public-reference>/ : exact snapshot

Only explicit public references are accepted, never User/Student/internal UUIDs.
No login is required; stale cookies do not gate public verification. Existing
PostgreSQL rate limits, no-store, 5 MiB file bounds, bounded multipart parsing and
HTTPS/gateway requirements are retained. Passport and version reference routes
share one 60/minute/IP budget; PDFs retain 10/minute/IP. Forwarded client addresses
are not trusted without the existing explicit gateway configuration.

Passport response keys: status, authentic, is_latest, passport_version,
latest_version, credential_status, credential_counts, source.
No Student names/emails/internal IDs, skill evidence, revocation reasons, issuer
administrative data, storage keys or paths are returned. Unknown references produce
NOT_FOUND. Existing-but-unissued/draft, empty or inconsistent issued snapshots are
UNVERIFIABLE, never valid. At most 500 snapshot credentials are evaluated; a larger
snapshot fails closed instead of silently omitting records.

For an issued snapshot with registered integrity:
- If ANY included credential is revoked, status is REVOKED.
- Otherwise, an invalid/untrusted/future-issued credential yields INVALID.
- Otherwise, an expired credential yields EXPIRED.
- Otherwise, status is VALID for latest or OUTDATED for historical versions.
credential_counts distinguishes all four current states, including mixed snapshots.
The public issuer allowlist AND trusted database issuer flag remain required.

PDF responses preserve their prior keys and add credential_status/credential_counts.
REVOKED and EXPIRED are new status values that API clients must handle. An authentic
old PDF is still authentic by registered bytes even when its credentials are revoked;
authentic/is_latest and current credential_status are independent facts. Never show
an overall green VALID label solely because authentic is true. The old Passport
regression expecting OUTDATED after revocation was updated to REVOKED while retaining
its authenticity/history assertions. No historical snapshot or document was rewritten.

An empty refreshed current Passport does not have a fabricated passport-wide
revocation flag: it reports UNVERIFIABLE. The old version/PDF still identifies the
revoked/expired included credentials. Unknown files with plausible PDF markers are
UNVERIFIABLE, not authentic; signature/EOF checks are not full syntax certification.
Public files are not rendered or parsed by a potentially expensive PDF engine.

## Database and transaction compatibility

No schema changes or migrations are required. Reference lookup is indexed by
existing unique public_reference columns. Snapshot membership uses existing
PassportVersionCredential foreign keys and uniqueness. Live credential and issuer
status is fetched in a single bounded query, not N+1 queries.

Verification performs no domain writes. Only the existing rate counters change.
A status is authoritative at its database read; a subsequent concurrent revocation
can change it after the response. No long-lived transaction/lock is held for public
verification, and clients must recheck current validity when making decisions.
The existing lifecycle outbox remains responsible for refreshing the latest
snapshot; live verification does not wait for it or publish new versions.

## Existing integrations/authentication validated

The combined tests exercise Classroom -> achievements -> credential -> durable
Passport refresh -> generated PDF -> public verification, plus duplicate and
concurrent imports, partial issuance recovery, source authorization, CSRF, account
isolation, deactivation, logout, OTP consumption and audit behavior. No unnecessary
replacement of authentication or import persistence was made.

Source trust is server-controlled. The simulated Classroom client remains separate
from ClassroomService recognition and the existing domain services. A future real
adapter must implement fetch_completions(), authenticate to an institution-controlled
host with deployment-provided credentials, verify TLS, and keep external I/O outside
inbox transactions. It must not accept arbitrary request-supplied hosts or source IDs.

Stable completion schema: event_id, student_id (external university ID), course_id,
completion_status, passed (boolean), finite grade, ISO completion_date; optional
course_name/enrollment_status remain descriptive. Source is fixed BTU_CLASSROOM.
Event IDs are immutable and namespaced; conflicting reuse is rejected. Repeated
identical events resume/skip rather than issuing again. Students/skills must already
exist; mappings come from the institutional catalog. Live synchronization still
requires explicit accounts.sync_classroom, verified active admin status and CSRF.

Spreadsheet sources require separate institutional approval and explicit import
permission. Cross-source aliases or changed upstream event IDs cannot safely be
inferred from Student/course alone; canonical institutional event identities remain
an upstream agreement. There is no claim of real BTU/Google/SMTP connectivity from
synthetic tests. Public verification never relies on untrusted completion payloads.

## Reproduce

Use Python 3.13, pinned requirements and a disposable local PostgreSQL instance on
127.0.0.1:55432 with a test-only postgres role. No .env or shared Neon URL is read by
the combined harness. From repository root:

```
PASSPORT_PYTHON=/absolute/path/to/venv/bin/python ./ops/test_backend.sh
```

Or set FOUNDATION_TEST_PG_HOST=127.0.0.1, FOUNDATION_TEST_PG_PORT=55432,
FOUNDATION_TEST_PG_PASSWORD (empty for disposable trust-auth DB only), and
AUTH_TEST_PG_PORT=55432, then use apps.integrations.postgres_test_settings.
The existing runner explicitly excludes the two legacy reference-schema comparison
tests; concurrency tests are executed. Performance measurements are documented
separately and are observations of a local fixture, not production certification.

Joint review should focus on the expanded public status contract and client handling,
issuer policy, proxy identity/rate limits and staging acceptance. No shared Neon
migration, production mutation or merge was performed. Stop after feature push and
wait for joint integration/testing.

The existing renderer's exact printed `passport-version:<public UUID>` verification
reference is accepted on both new routes and selects that exact historical version.
A regression generates a real PDF, extracts its printed reference, and verifies it
through the public API. No renderer format or PDF metadata trust was introduced.
Unsupported prefixes (including Student references) remain NOT_FOUND.
