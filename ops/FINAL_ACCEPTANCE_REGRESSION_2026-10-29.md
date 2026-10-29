# Final acceptance regression and integration candidate — 2026-10-29

This report supersedes the incomplete full-regression status in
`WEBSITE_ACCEPTANCE_2026-10-29.md`, which remains the historical initial-run record.

## Git and scope

Repository: https://github.com/samkharadzesopio/AI-Skills-Digital-Passport

Branch: `test/full-website-acceptance-20261029` in
`/workspace/AI-Passport-website-acceptance-20261029`.
Starting baseline and latest fetched shared head at review:
`319449d53825c6bc888b7c780130ee8eb320a534` (`origin/integration`).
It includes the reviewed React/Django sources, Google Student authentication,
spreadsheet imports, immutable PDFs and existing blockchain lifecycle.
The original checkout remains clean on `feature/passport-blockchain-proof` at
`858e1b7`. Both worktrees, local branches and the empty stash list are preserved.
No reset, stash, branch overwrite, merge, public transaction or push was used.

Only these acceptance files belong to the candidate:

- `backend/apps/blockchain/services.py`
- `backend/apps/blockchain/tests.py`
- `ops/run_isolated_tests.py`
- `ops/test_verification_e2e.py`
- `ops/WEBSITE_ACCEPTANCE_2026-10-29.md`
- `ops/FINAL_ACCEPTANCE_REGRESSION_2026-10-29.md`

No migrations, dependencies, lockfiles, PDF design, React runtime, credential
services, legal-name workflow or shared database configuration changed.

## Fix review

1. **Pre-signing PDF validation.** The integrated document service performs its
   immutable artifact check before opening the stream. Its ValidationError for
   byte-integrity rejection is now translated to existing terminal
   `PDF_STORAGE_MISMATCH`. Storage OSErrors wrapped by the same service retain
   retryable `CHAIN_OR_STORAGE_UNAVAILABLE`; exception text and private storage
   paths are not exposed. Permission and unrelated errors are not caught by the
   new handler. Existing worker error handling remains in place.

   Validation occurs before signing/nonce allocation and outside a database
   transaction. Existing `_record()` atomically stores the state and retry policy;
   no transaction, locking, idempotency, signature, proof or authorization logic
   changed. Public proof consumers retain the existing FAILED/PENDING semantics
   and cannot gain a verified badge from the rejection. Signed bytes, confirmed
   receipts and cancellation dependencies remain immutable.

   Regression: corrupt bytes are terminal, not retryable, with no signed
   transaction or nonce. A new real-filesystem regression removes the PDF,
   verifies retryable PENDING with no signature/nonce, restores exact original
   bytes and verifies the same operation reaches CONFIRMED.

2. **Concurrent nonce fixture.** A renderer change no longer creates another PDF
   for an issued immutable version. The test now changes a synthetic academic
   program, publishes a distinct version through the existing service and asserts
   distinct document IDs before concurrent signing. The original distinct-nonce
   and successful-confirmation assertions remain intact.

3. **Expired verification fixture.** Creating a historical credential with an
   award earned today violates the authoritative earned-date contract. The fixture
   clock is frozen at historical issuance, then restored before current public
   verification. Expiration, authenticity and public-verdict assertions are
   preserved; no production date validation changed.

The runner's documented `--blockchain-regression` selects the complete existing
blockchain app suite. It neither excludes tests nor changes assertions.

## Complete backend execution

Configuration: Python 3.13.5, Django 6.1.2, psycopg 3.3.6, PostgreSQL 17.11,
`apps.integrations.postgres_test_settings`, existing foundation test runner.
The interpreter is `/workspace/AI-Skills-Digital-Passport/.venv-auth/bin/python`.
The cluster is newly initialized on a dynamically allocated loopback port using
trust authentication only for disposable local tests; it is stopped and removed
by the owned-resource runner. Production settings and Neon are never loaded.

Exact complete backend command (from the candidate worktree):

```sh
env TMPDIR=/dev/shm \
 BTU_TEST_ARTIFACTS=/tmp/btu-final-regression-20261029-artifacts \
 PASSPORT_PG_BIN=/tmp/btu-phase1-tools/pg-bin \
 BTU_BROWSER_TOOLS=/tmp/btu-live-browser-tools \
 BTU_BROWSER_EXECUTABLE=/usr/bin/chromium \
 /workspace/AI-Skills-Digital-Passport/.venv-auth/bin/python -u -B \
 ops/run_isolated_tests.py --backend
```

The runner invokes `backend/manage.py test apps.api apps.integrations apps.skills
apps.credentials apps.passports apps.students apps.accounts apps.verification
apps.blockchain --settings=apps.integrations.postgres_test_settings --verbosity=1`.

**PASS: 676 discovered; 674 executed and passed; 0 failed; 0 errored; 0 skipped;
436.110 seconds.** The one additional test explains the increase from 673 to 674.
The same two inherited exclusions remain, separate from executed/skipped counts:

- `apps.skills.tests.SkillPostgreSQLTests.test_reference_schema_matches_migration`
- `apps.students.tests.StudentPostgreSQLTests.test_reference_schema_matches_migration_and_preserves_foreign_keys`

These legacy SQL comparisons were not newly excluded or represented as passed.
The guard suites (4 approval, 10 resources, 3 local-profile checks), system check,
migration-drift check and verified owned cleanup also passed. Expected injected
failure/rate-limit messages in test output are not failed test results.

## Post-regression validation

Solidity 0.8.30, locked Foundry/Anvil 1.7.1 and Node 24.19.0 were used.
Fresh results after the complete backend pass:

| Gate | Result |
| --- | --- |
| Solidity artifact comparison | PASS, exact ABI/bytecode/runtime match |
| Foundry | PASS, 12 passed, zero failed/skipped |
| Complete Django blockchain app | PASS, 102 passed in 268.738 seconds |
| Immutable issued PDF no-regeneration regression | PASS |
| Automatic award -> Passport/PDF -> Anvil | PASS, independently checked commitment and original/altered bytes |
| Real HTTP/Anvil lifecycle | PASS, all 11 journeys, three confirmations, five separate-client proof checks |
| Frontend | PASS, all 14 commands after layout environment correction below |
| Graphical Passport layout | PASS, seven viewports, all 33 variable-content pages |

The first layout invocation stopped before browser launch with EROFS creating a
Playwright temporary directory in `/var/tmp`. The unchanged check passed after
setting TMPDIR to a new directory created by `mktemp -d
/tmp/btu-final-layout-XXXXXX`. No layout assertion, timeout or source was changed.
The build retains the existing large-chunk advisory. Public HTTP: PASS, 35 real
proxied requests. Student HTTP: PASS, 65 requests. Admin/Student/public HTTP:
PASS, 146 requests. Graphical Chrome/Django: PASS, six journeys, seven viewports,
97 actual API responses. Final owned cleanup passed. jsdom drivers emit existing
React act() advisory messages, distinct from the native graphical browser suite.

## Shared-head advancement discovered after these passes

The final fetch found `origin/integration` had advanced to
`64a1cd589597f00b97a624cd49db84f0e4989ec2`, adding `68c8d21` Workspace portal
authentication and its existing `accounts.0009_workspace_portal` migration.
The results above cover `319449d` plus acceptance corrections. A protected local
backup will preserve that tested candidate before applying only its acceptance
commit atop the newer integration head. No shared branch is merged or rewritten.
Updated-baseline validation is required before integration readiness is declared.

Exact service rerun uses the same environment above, with
`BTU_TEST_ARTIFACTS=/tmp/btu-final-services-20261029-artifacts`:

```sh
python -u -B ops/run_isolated_tests.py --blockchain-regression --automatic-passport --ui-http --browser-http
```

Solidity commands use
`SOLC_PATH=/tmp/btu-phase1-tools/solc-0.8.30` and
`FOUNDRY_CACHE_PATH=/tmp/btu-final-forge-cache`:

```sh
npm --prefix blockchain run check
npm --prefix blockchain test
```

Frontend commands are `npm --prefix frontend run NAME` for each of:
`build`, `lint`, `check:architecture`, `check:integration`, `check:auth`,
`check:student`, `check:verification`, `check:spreadsheet`, `check:admin`,
`check:passport`, `check:passport-card`, `check:demo`, `check:preview`,
`check:passport-layout`. `VITE_ENABLE_DEMO=false` except true for the explicit
preview-only check. Graphical tests use separate local Playwright/Chromium tools.

Evidence logs, outside Git:

- `/tmp/btu-final-backend-regression-20261029.log`
- `/tmp/btu-final-services-20261029.log`
- `/tmp/btu-final-solidity-20261029.log`
- `/tmp/btu-final-frontend-20261029.log`
- `/tmp/btu-final-layout-20261029.log`

The environment injects `.git` markers above ordinary writable temp roots;
credential protections correctly reject files under those roots. Disposable
backend fixtures run in `/dev/shm` outside Git with execution permission. No
credential guard was bypassed. The earlier missing-artifact-directory invocation
was corrected by supplying `BTU_TEST_ARTIFACTS`, without changing application code.

## Integration and remaining scope

The single commit containing this final report is the candidate. Resolve its full
hash with `git log -1 --format=%H -- ops/FINAL_ACCEPTANCE_REGRESSION_2026-10-29.md`.
Publishing and merging require separate explicit approval. No force push or
shared-history rewrite is needed.

After approval, publish this test branch with an ordinary push. From the team's
clean integration checkout, fetch and compare the actual remote head before
integrating; if it has advanced beyond the tested baseline, stop and validate the
combined candidate rather than treating this report as covering new code.

```sh
# Testing worktree, only after approval:
git push -u origin test/full-website-acceptance-20261029
# Clean integration checkout, only after merge approval:
git fetch origin
git switch integration
git pull --ff-only origin integration
git merge --ff-only origin/test/full-website-acceptance-20261029
# Only after final shared-head review/approval:
git push origin integration
```

No shared Neon migrations are necessary for these corrections. Existing baseline
migrations remain a separate deployment responsibility.

This task does not implement the Skills Gap Analyzer UI, redesign the website or
prove real BTU endorsement. Public Amoy, real Google Sheets/OAuth, real Classroom,
SMTP, Chrome-extension acceptance and deployed hosting remain externally untested.
Synthetic local services and real Anvil transactions do not establish those claims.
