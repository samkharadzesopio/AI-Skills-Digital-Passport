# Student/Admin API development report

Branch: `feature/student-admin-apis`.
Baseline: freshly fetched `origin/integration` at `f8057c556822683e8baa2a7e3835be45876b958a`.
Implementation commit hash is supplied in the completion message and is available
with `git rev-parse feature/student-admin-apis`. No feature branches were merged.

The complete endpoint inventory, request/response contracts, errors, filters,
pagination, permission matrix, and integration notes are in [STUDENT_ADMIN_APIS.md](STUDENT_ADMIN_APIS.md).

## Files created

- `backend/apps/api/__init__.py`
- `backend/apps/api/queries.py` — shared eager query plans and SQL aggregations.
- `backend/apps/api/serializers.py` — explicit response contracts and strict write validation.
- `backend/apps/api/views.py` — student/admin service adapters and permissions.
- `backend/apps/api/urls.py` — 18 routes covering 20 method/path combinations.
- `backend/apps/api/tests.py` — 24 private API, integration, PDF, security, and query-efficiency tests.
- `backend/apps/skills/migrations/0003_skill_subcategory.py`
- `backend/apps/passports/migrations/0006_snapshot_subcategory.py`
- `ops/STUDENT_ADMIN_APIS.md`
- `ops/STUDENT_ADMIN_REPORT.md`

## Files modified

- `backend/apps/skills/models.py` — optional catalog subcategory with Python/SQL empty defaults.
- `backend/apps/passports/models.py` — corresponding immutable snapshot field.
- `backend/apps/passports/services.py` — freeze/hash subcategory and fix keyword-only refresh callback.
- `backend/apps/passports/document_services.py` — frozen subcategory in PDF context.
- `backend/passport_pdf_renderer.py` — classification label and new renderer fingerprint version.
- `backend/config/urls.py` — private API routing alongside existing routes.
- `backend/config/auth_test_urls.py` — same routes under the isolated test harness.
- `backend/apps/passports/tests.py` — accurate keyword-only mock and lifecycle/concurrency receipt expectations.
- `backend/apps/integrations/test_classroom_automation.py` — verify successful immediate lifecycle refresh.
- `backend/apps/integrations/test_full_workflow.py` — verify worker replay after immediate processing.
- `ops/test_backend.sh` — include the private API suite in standard regression.

## Security and domain integration

Existing session authentication/CSRF, authoritative student account linkage,
`IsStudent`, credential/passport object permissions, `has_admin_permission`,
`IsAdminWithPermission`, and `AuditedAPIView` are reused. Read/write permissions are
separate. University identities and account links cannot be patched through these
APIs. Collections are paginated and nested skill achievements bounded. Source
payloads, credentials' internal fingerprints, and account/authentication metadata
are excluded from serializers.

Existing `issue_credential` and `revoke_credential` retain fixed BTU issuer identity,
idempotency, verified award validation, lifecycle events, and transactional refresh
outbox writes. Existing `verification_status_at` determines response validity;
SQL counts/filters match its state precedence. Existing passport services own
publication/versioning and immutable snapshots. Public verification is unchanged.

A real existing callback defect was exposed by executing post-commit callbacks:
`process_passport_refresh_event` requires a keyword-only `refresh_id`. The caller
now supplies it correctly. Existing tests that inadvertently depended on the broken
callback were updated to verify successful immediate publication and safe replay.

## Database and subcategories

Two additive migrations add optional subcategory fields (default empty) and extend
the PostgreSQL snapshot insertion guard. No categories are reinterpreted, no
historical classifications invented, and no issued content hashes rewritten.
The field is frozen into new passport versions and rendered from that snapshot.
SQL defaults preserve legacy raw inserts. Existing immutability and all other
constraints remain enforced. Migrations were exercised only in disposable local
PostgreSQL; no shared Neon database was accessed or migrated.

No institution-approved subcategory vocabulary was supplied. Empty legacy values
remain empty; catalog population/governance is an integration responsibility.

## Verification

Local Python: existing `../AI-Skills-Digital-Passport/.venv/Scripts/python.exe`.
Test database: a newly initialized disposable PostgreSQL 18 cluster bound only to
`127.0.0.1:55439`, using the existing loopback-only settings. No `.env` or production
`DATABASE_URL` was loaded. The full suite command is:

```powershell
$env:FOUNDATION_TEST_PG_HOST = '127.0.0.1'
$env:FOUNDATION_TEST_PG_PORT = '55439'
$env:FOUNDATION_TEST_PG_PASSWORD = 'local-test-only'
$env:AUTH_TEST_PG_PORT = '55439'
$python = '../AI-Skills-Digital-Passport/.venv/Scripts/python.exe'
& $python backend/manage.py test apps.api apps.integrations apps.skills apps.credentials apps.passports apps.students apps.accounts apps.verification --settings=apps.integrations.postgres_test_settings --verbosity=1 --noinput
& $python backend/manage.py check --settings=apps.integrations.postgres_test_settings
& $python backend/manage.py makemigrations --check --dry-run --settings=apps.integrations.postgres_test_settings
& $python -m compileall -q backend/apps/api backend/apps/skills/migrations/0003_skill_subcategory.py backend/apps/passports/migrations/0006_snapshot_subcategory.py
git diff --check
```

Final combined run: **389 tests passed in 88.794 seconds; 0 failures, 0 errors, 0 skipped.**
391 tests were discovered; the existing harness explicitly excluded the two tests below.
Django system checks: no issues. Migration consistency: no changes detected.
Source compilation and `git diff --check` both passed.

The standard combined runner intentionally excludes these two legacy reference-SQL
rebuild tests; they were not executed, and were not silently counted as passes:

- `apps.skills.tests.SkillPostgreSQLTests.test_reference_schema_matches_migration`
- `apps.students.tests.StudentPostgreSQLTests.test_reference_schema_matches_migration_and_preserves_foreign_keys`

The targeted rerun of private APIs and affected existing regressions passed 27 tests
before two further input/bounded-history/snapshot-guard tests were added. Earlier
iterations failed due to test fixture setup, missing SQL defaults, and old callback
expectations; these were corrected before the final full run. Failure/retry log
messages emitted by refresh recovery tests are intentional fault-injection coverage.

Query-efficiency tests compare small and larger pages: credential/skill collection
queries do not grow per item; admin student lists and statistics stay constant as
students are added. The suite also contains an existing 5,000-identity database
check. This is not a concurrency or load benchmark.

## Limitations and next phase

- No deployment, frontend modifications, or merge into integration/main was performed.
- No measured concurrent-user capacity is claimed.
- Raw evidence blobs/URLs remain private until an approved safe evidence contract exists;
  award ID and course reference are available to students.
- PATCH deliberately restricts university identity fields; institutional corrections
  still require the established trusted workflow.
- Snapshot history represents issuance-time facts. Current credential validity and
  public verification should be used for live trust decisions.
- Existing outbox/expiry workers remain necessary; monitor retries and failures.

Next phase: jointly review the JSON contracts and subcategory vocabulary, apply
migrations to an isolated staging copy, run frontend/verification/worker regressions,
then load-test realistic university data and recovery behavior before deployment.
