# Credential investigation: commit 0e77773

Investigation date: 2026-10-26. No credential values are included here.

## Finding

**Synthetic test credential by source provenance; live environment reuse is not
independently verified.** The flagged login in
`frontend/scripts/check-verification-http.mjs` matches the Admin created by
`PassportPDFAPITests.setUp` in `backend/apps/api/test_pdf.py`. The creation first
appears in commit `c29ab1d`; the HTTP consumer appears in `0e77773`. This is an
application password fixture, not an SMTP/company-mailbox password configuration.

The harness imports `apps.integrations.postgres_test_settings`, which imports
`config.auth_test_settings` and `config.foundation_test_settings`. These do not
load production settings or `.env`; the foundation settings require an explicit
loopback host, and authentication settings pin PostgreSQL to loopback. The
original HTTP runner created a Django test database, created the fixture there,
and authenticated through a loopback WSGI server and Vite proxy.

The Admin password backend checks the application's User table. The credential
would also authenticate in another environment **if someone copied that account
and password there**. Neither its email domain nor a test-looking name establishes
exclusive scope. No mailbox login was attempted.

## Search evidence and limits

- Current tracked files contained the flagged pair only in the PDF fixture and
  verification HTTP consumer. All locally reachable refs were searched; the
  pair's introducing changes were the two commits above.
- Pattern scan of 656 reachable Git blobs covered private-key headers, common
  cloud/GitHub tokens, credential-bearing URLs and literal secret assignments.
  URL matches were negative validation fixtures. Other literal matches were test
  fixtures/settings/documentation. No additional confirmed external-service
  credential was identified by this scan. This is a heuristic scan, not proof
  that every possible secret format is absent.
- Historical Django settings contained committed development-marked signing
  keys. Current deployment settings require an environment-provided signing key.
  If any deployment ever used a historical key, rotate that deployment's Django
  signing key and invalidate affected sessions/tokens; do not retain the exposed
  key as a verification fallback.
- 239 local configuration/log files across the workspace were checked for the
  flagged pair with no matches. Existing local databases, demo accounts and
  existing processes were preserved. Neon/production databases, deployed secret
  stores and mailbox services were not queried. Their account/password reuse
  remains unverified; an operator should check account existence and password
  hashes without exporting hashes or attempting public logins. If matched,
  rotate that application's Admin password immediately and revoke its sessions.
- `origin/integration` was fetched before preparing the remediation. Historical
  exposure remains in Git; no history rewrite is part of this remediation.

## Remediation and cleanup contract

The PDF fixture now generates a random account identifier and random password.
The verification harness supplies a fresh password to its HTTP driver through
an ephemeral environment payload, marked test-only. The driver removes its copy
from the environment after parsing it. Admin HTTP fixture passwords are also
generated per run. No new password is written to source or logs.
Test settings also generate their Django signing keys in memory.

`config.disposable_tests.DisposableRun` owns unique test database names, temporary
media, process-local mail/cache artifacts and HTTP servers. It atomically creates
its database, refuses any pre-existing name, registers Django teardown before
migration, and verifies removal afterward. ExitStack attempts every registered
cleanup even if another cleanup fails. SIGINT/SIGTERM unwind cleanup. The combined
backend runner refuses keepdb and parallel clones and uses this same manager.

Run the complete acceptance suite with:

```powershell
python ops/run_isolated_tests.py --full
```

Use the repository virtual environment. The Windows default binary directory is
`C:/Program Files/PostgreSQL/18/bin`; set `PASSPORT_PG_BIN` on other installations.
`ops/test_backend.sh` invokes the same launcher with `--backend`. The launcher creates a fresh loopback-only PostgreSQL
cluster, runs cleanup regressions and the combined backend/Student/Admin/public
verification suites, then stops only its cluster and removes its temporary
directory. Django/Vite are in-process or in the child explicitly started by the
run; children are killed and reaped on timeout/interruption. This suite starts no
Anvil process and submits no public-chain transactions. No historical blockchain
transaction is removed or claimed removable.

Cleanup regressions cover injected migration failure, application failure,
KeyboardInterrupt, cleanup callback failure, child interruption, server shutdown,
temporary PDF/upload/OTP/session artifacts, database disappearance, and refusal
to adopt a pre-existing database. Domain records, including Students, Admins,
achievements, credentials and Passport versions/documents, disappear with the
owned database. Existing local demo Student/Admin accounts remain untouched.

A forced OS termination, machine crash, or uncooperative filesystem can prevent
finally blocks from completing. No infrastructure can guarantee execution after
SIGKILL/power loss. Preserve any ownership-uncertain resource and report it;
never run wildcard database/process/filesystem cleanup. Legacy standalone test
settings and arbitrary direct test commands are not made universally safe by
this launcher; use this entry point for the combined automated suite.

## Validation results

- Combined backend: 469 passed. The existing runner continues to exclude two
  legacy reference-schema SQL tests; they were not executed.
- Real public verification, Student and Admin HTTP acceptance: all passed,
  including generated Admin passwords, actual PDFs/uploads and OTP sessions.
- Final cleanup regressions: six passed, plus three local-boundary tests through
  the managed Django runner. Real PostgreSQL checks exercised migration failure,
  application failure, interruption, refusal/preservation of an existing DB,
  and rejection of libpq redirection.
- Migration drift check: no changes. JavaScript syntax and Git whitespace checks
  passed. Existing React act warnings and rate-limit proxy reset diagnostics did
  not fail HTTP acceptance.
- Both final isolated runs verified cluster shutdown and removal of their
  temporary directories. Process inventory afterward found no test-owned Python,
  Node/Vite or PostgreSQL process remaining. No current-run test records, PDFs,
  uploads, OTP files, session files or Vite caches remain. No Anvil was started.
- Existing workspace services, databases, logs/caches and intentionally
  provisioned demo accounts were preserved. Earlier failed attempts also disposed
  of their fresh clusters; no ownership-uncertain resource was deleted.

Do not close the live-reuse question solely on the basis of this source review.
There is no confirmed genuine company-mailbox credential exposure here, and no
external-service rotation was performed. Live deployment checks described above
remain the operator follow-up before claiming exclusive test-only use.
