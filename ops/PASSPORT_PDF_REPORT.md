# Secure Passport PDF API development report

Branch: `feature/passport-pdf-apis`.
Baseline: local `integration` at `b9343110dff8c664f4719867080855fd165fa001`, exactly the
requested commit. The feature worktree is `AI-Passport-pdf-apis`. No other worktree
was replaced or removed. The final feature commit hash is supplied in the completion
message and can be obtained with `git rev-parse feature/passport-pdf-apis`.

## Delivered APIs

| Method | Student endpoint |
|---|---|
| POST | `/api/student/passport/pdf/` |
| GET | `/api/student/passport/pdf/status/` |
| GET | `/api/student/passport/pdf/download/` |
| POST | `/api/student/passport/versions/{id}/pdf/` |
| GET | `/api/student/passport/versions/{id}/pdf/status/` |
| GET | `/api/student/passport/versions/{id}/pdf/download/` |

| Method | Administrator endpoint |
|---|---|
| POST | `/api/admin/passports/{id}/pdf/` |
| GET | `/api/admin/passports/{id}/pdf/status/` |
| GET | `/api/admin/passports/{id}/pdf/download/` |

All admin endpoints accept the same optional `version_id` UUID query selector for
an issued version belonging to that passport. No client student ID or storage path
is accepted. Full contracts, route names, status/error behavior, rate limits and
permission choices are documented in [PASSPORT_PDF_APIS.md](PASSPORT_PDF_APIS.md).

## Files changed

Created:

- `backend/apps/api/pdf_serializers.py` — validated selectors and public-safe private metadata.
- `backend/apps/api/pdf_throttles.py` — existing persistent account counters bound generation.
- `backend/apps/api/pdf_views.py` — shared Student/Admin service adapters and file streaming.
- `backend/apps/api/pdf_urls.py` — nine named routes.
- `backend/apps/api/test_pdf.py` — 24 targeted API/reliability/rendering tests.
- `ops/PASSPORT_PDF_APIS.md` — API integration contract.
- `ops/PASSPORT_PDF_REPORT.md` — this report.

Modified:

- `backend/apps/api/urls.py` — include the PDF routes alongside existing APIs.
- `backend/apps/passports/document_services.py` — optional backward-compatible
  `wait_seconds` override; the API uses zero to avoid waiting on competing generation.
- `backend/passport_pdf_renderer.py` — preserve the existing template while checking
  unsupported/overflow text; fill supplement classification and align with original
  table cells; advance renderer fingerprint version.
- `backend/apps/verification/test_passport_verification.py` and
  `backend/apps/verification/test_performance.py` — resolve the fixture's lazy passport
  relation before measuring verifier query counts. Production verification code and
  response contracts remain unchanged.

No models, migrations, dependencies, frontend files, PDF template or stamp assets changed.

## Reused services and security

The APIs reuse `generate_passport_document`, `open_passport_document_for_student`,
existing document metadata/leases/hash/fingerprint/storage-key validation,
`get_authenticated_student_id`, `IsOwnPassport`, `IsAdminWithPermission`,
`AuditedAPIView`/`SecurityAudit`, and `AuthRateLimitBucket`. Existing snapshot and
credential lifecycle services remain the sole authority; no new generator, queue,
role model or database was introduced.

Student versions are scoped to authenticated canonical identity and checked with
object permissions; the opening service checks ownership again. Admin generation
requires `accounts.manage_credentials`; status/download require
`accounts.view_student_records`. Both apply the existing verified active ADMIN/staff,
non-superuser policy. Privileged generation and GET/HEAD downloads record attempts
and HTTP outcomes. Authentication remains existing session authentication plus CSRF.

PDFs stream as attachments with a UUID-based filename, no-store/no-cache headers and
nosniff. File resources close with the response, including explicit cleanup on
construction failures. Metadata excludes storage keys, lease tokens, exception text
and filesystem paths. Public verification references do not grant private access.

Rendering is bounded, synchronous and outside request transactions (also marked
non-atomic for ATOMIC_REQUESTS deployments). The existing service retains short
claim/finalization transactions and idempotency. Repeated/concurrent requests reuse
one document; an active lease returns 409 and Retry-After, without inventing an
asynchronous acceptance. Failed requests remain durable and can retry using the same
reference. Six POST requests/minute/account is the default shared-worker limit;
status polling does not consume it.

Historical requests use immutable snapshots. Current mutable profiles/catalog changes
cannot alter their identity/classification. Existing registered documents/hashes remain
untouched. Public PDF/reference verification still distinguishes byte authenticity,
version currency and current revoked/expired credential validity.

## Actual testing

Environment: existing repository Python 3.13 virtual environment and a disposable
PostgreSQL 18 cluster on `127.0.0.1:55439`. Existing loopback-only settings were used;
no production `.env`/DATABASE_URL or shared Neon database was loaded. Variables were
`FOUNDATION_TEST_PG_HOST=127.0.0.1`, `FOUNDATION_TEST_PG_PORT=55439`,
`FOUNDATION_TEST_PG_PASSWORD=local-test-only`, and `AUTH_TEST_PG_PORT=55439`.

Commands (Python executable abbreviated as `$python`):

```powershell
$python = '../AI-Skills-Digital-Passport/.venv/Scripts/python.exe'
& $python backend/manage.py test apps.api apps.passports apps.accounts apps.verification apps.integrations.test_full_workflow --settings=apps.integrations.postgres_test_settings --noinput --verbosity=1
& $python backend/manage.py check --settings=apps.integrations.postgres_test_settings
& $python backend/manage.py makemigrations --check --dry-run --settings=apps.integrations.postgres_test_settings
& $python -m compileall -q backend/apps/api/pdf_views.py backend/apps/api/pdf_serializers.py backend/apps/api/pdf_throttles.py backend/apps/api/pdf_urls.py backend/apps/api/test_pdf.py backend/passport_pdf_renderer.py
git diff --check
git diff --exit-code b934311 -- backend/templates backend/stamps
```

Results:

- Focused regression: **203 tests passed in 136.381 seconds**, 0 failures/errors/skips.
  This includes all 24 new PDF API tests, existing private API tests, Passport/PDF
  services, authentication, public verification, and the Classroom-to-PDF workflow.
- Final three directly affected smoke tests passed in 2.827 seconds after tightening
  the cover-name boundary and invalid throttle-setting error handling.
- Django system check: no issues. Migration consistency: no changes detected.
  Source compilation and whitespace checks passed. Template/stamp diff is empty.
- Actual generated/downloaded bytes were SHA-256 checked against registered metadata;
  PDF text, template pages, stamps, category/subcategory, version and credential
  references were exercised. Public upload verification passed VALID, REVOKED and
  EXPIRED cases while retaining authenticity semantics.
- Concurrent HTTP requests rendered once, returned 200/409 with one document
  reference, and observed no rendering transaction. Failure/retry, existing-file
  reuse, renderer-change fallback, file closure, CSRF, permissions, paths, missing
  records, request budgeting and query bounds were covered.
- A five-page synthetic preview was rendered with the existing renderer and rasterized
  with PyMuPDF for visual inspection of all pages; supplement alignment was corrected
  against actual template drawing coordinates. A geometry assertion covers multiple
  supplement pages and skills beyond the first ten cards. Poppler was unavailable;
  no additional rendering dependency was installed.

Earlier runs and baseline audit:

- Initial 21-test API run had one test cleanup error from an unclosed streaming test
  response; the response now closes. Functional API checks passed.
- The first focused 203-test run had two query-count assertion failures. Both were
  reproduced on untouched `integration` (`b934311`) using a separate disposable
  database: the fixture lookup contributed a third query inside an assertion intended
  to measure only the verifier. Resolving that reference before measurement preserves
  the actual two-query contract and fixes both tests without changing verification.
- Deliberate renderer/storage and public throttle/upload failures emit expected safe
  log messages during tests. They are not unreported test failures.
- No complete full-backend regression was run in this feature phase. No tests in the
  selected 203-test suite were skipped or excluded; the runner's two legacy schema
  comparisons are outside this focused selection.

## Limitations and integration considerations

- The fixed template's existing font cannot represent Georgian and some other
  characters faithfully. Such snapshots now return safe 422 instead of a corrupted
  identity. Long fields/box overflow also return 422; they require a reviewed future
  font/layout policy. The template itself has not been redesigned.
- Generation is synchronous within existing row/byte bounds; no HTTP load or
  concurrent-user capacity claim is made. Existing service-level leases remain in force.
- Status availability reflects issued metadata; an external storage loss/outage is
  reported safely at download time. Issued files are not regenerated or overwritten
  merely because storage is missing. Operational recovery remains an administrative
  storage responsibility.
- GET/HEAD download audit status records HTTP outcome, not guaranteed end-to-end
  delivery. Status polling itself is not audited as a privileged download.
- Future work touching `apps/api/urls.py`, the optional document service signature,
  renderer version/layout checks, or the two verification test measurements should
  retain these additions during merge review. The branch is based on locally merged
  integration history that is intentionally still ahead of origin/integration.
- No integration/main merge, shared database migration, deployment, real BTU API,
  frontend change or worktree removal was performed.

Recommended next task: institution-reviewed multilingual font support and bounded
field policy for the existing BTU template, followed by joint staging validation of
private HTTP downloads, storage recovery and frontend integration.
