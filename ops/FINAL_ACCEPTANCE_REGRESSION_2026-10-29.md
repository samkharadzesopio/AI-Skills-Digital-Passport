# Final acceptance regression and integration candidate — 2026-10-29

This report supersedes the incomplete full-regression status in
`WEBSITE_ACCEPTANCE_2026-10-29.md`, which remains the historical initial-run record.

## Git and scope

Repository: https://github.com/samkharadzesopio/AI-Skills-Digital-Passport

Original testing branch: `test/full-website-acceptance-20261029` in
`/workspace/AI-Passport-website-acceptance-20261029`.
Initial starting baseline and shared head at the first review:
`319449d53825c6bc888b7c780130ee8eb320a534` (`origin/integration`).
It includes the reviewed React/Django sources, Google Student authentication,
spreadsheet imports, immutable PDFs and existing blockchain lifecycle.
The updated integration parent is `64a1cd589597f00b97a624cd49db84f0e4989ec2`;
the validation of this newer source is recorded separately below.
The original checkout remains clean on `feature/passport-blockchain-proof` at
`858e1b7`. Both worktrees, local branches and the empty stash list are preserved.
No reset, stash, branch overwrite, merge, public transaction or push was used.

Only these acceptance files belong to the candidate:

- `backend/apps/blockchain/services.py`
- `backend/apps/blockchain/tests.py`
- `frontend/scripts/check-admin-http.mjs`
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

4. **New Workspace baseline's Admin HTTP driver.** The latest team UI replaces
   the old email/OTP login form with Workspace sign-in. Its Student/graphical
   drivers were updated upstream, but the Admin HTTP driver still waited for the
   removed form and timed out after the latest full backend pass. It now uses
   the same existing `requestStudentOtp`/`verifyStudentOtp` services as the Student
   HTTP driver, with the real server's private fixture mailbox, then renders the
   dashboard and retains all ownership, revoked-state and permission assertions.
   This is API-driven fixture login, not a claim to click an OTP form that no
   longer exists. Workspace UI remains independently covered by the five-group
   graphical check. No response, session, permission or OTP verification is mocked.
   JavaScript syntax and lint checks passed after this driver-only correction.

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

The subsequent fetch found `origin/integration` had advanced to
`64a1cd589597f00b97a624cd49db84f0e4989ec2`, adding `68c8d21` Workspace portal
authentication and its existing `accounts.0009_workspace_portal` migration.
The results above cover `319449d` plus acceptance corrections. That tested
candidate was committed as `0e49d1b` and preserved on
`review/acceptance-fixes-319449d-20261029`. Its unpublished acceptance commit was
rebased cleanly atop the newer shared head in the same worktree; the team changes
and our separate runner options were retained without manual conflict resolution.
No shared branch was merged, published or rewritten.

### Updated baseline validation

The exact newer-baseline command uses the same environment and interpreter as
above, with `BTU_TEST_ARTIFACTS=/tmp/btu-final-latest-20261029-artifacts`:

```sh
python -u -B ops/run_isolated_tests.py --backend --google-auth-browser --ui-http --browser-http
```

**PASS full backend on `64a1cd5` plus acceptance fixes: 681 discovered; 679
executed and passed; 0 failed, 0 errored, 0 skipped; 549.996 seconds.** Only the
same two existing legacy SQL comparisons were excluded. All 102 blockchain
tests, including storage recovery and distinct-document concurrency, are included
in that complete pass. No tests were newly excluded.

The updated Workspace portal graphical acceptance passed five groups and 47
actual local API responses using synthetic FedCM/keys, with no live Google.
All 14 frontend commands were rerun on the newer source and passed, including
seven viewports and all 33 variable-content pages. The newer frontend batch used
a fresh writable temporary directory from the outset and needed no source fix.

After correcting the stale Admin OTP-form driver, the newer-baseline real HTTP
batch passed again: 11 Anvil lifecycle journeys, 35 public requests, 64 Student
requests and 146 Admin/Student/public requests. Final graphical Chrome/Django:
six journeys, seven viewports and 90 actual API responses passed, with no API
interception. All owned servers, signer/mailbox/media fixtures and disposable
databases were cleaned. A complete backend follow-up was then requested on the
same backend source; its final result is recorded at delivery below.

The required complete backend follow-up after the Admin-driver correction also
passed: **679 passed in 504.099 seconds; 681 discovered, two inherited exclusions,
zero failed/errored/skipped**. Command: the documented isolated environment with
`BTU_TEST_ARTIFACTS=/tmp/btu-final-after-ui-20261029-artifacts`, then
`python -u -B ops/run_isolated_tests.py --backend`. Owned cleanup passed.

## Final all-development-branches audit

The user subsequently authorized normal non-force integration and push of all
completed intended work. Every existing local branch/worktree, dirty file and
stash was inspected again, and all remote heads were fetched. All eight original
development feature tips are already ancestors of `origin/integration`:

| Local development branch | Tip already integrated |
| --- | --- |
| feature/blockchain-mvp-completion | c87f801 |
| feature/classroom-credential-automation | c64d4a2 |
| feature/dev2-automation-verification | 385896b |
| feature/integration-verification | 72fdd4b |
| feature/passport-blockchain-proof | 858e1b7 |
| feature/passport-chrome-extension | f497c5e |
| feature/public-verification-integration | 50db374 |
| feature/rule-based-course-recommendations | f497c5e |

The `work` branch at 46c8e56 is also included. Remote credential/Passport
automation, flexible-spreadsheet, Passport core/PDF/API, blockchain stabilization
and complete-blockchain candidate tips were checked and are also included.
The older `fix/frontend-blockchain-compatibility` commit 565d2c1 is by teammate
samkharadzesopio, is not an ancestor, and contains an older provisional proof UI;
it was not merged over the newer reviewed integrated React implementation.
The prior report already lists other historical teammate frontend refs.

Only the acceptance work remains to add. The review backup 0e49d1b represents
the earlier version of that same work, not an independent feature to merge.
The rebased acceptance commit 1bbd418 carries those fixes onto 64a1cd5. A final
commit records the newly validated Admin test-driver correction and complete
handoff. No duplicate models/services/features or unnecessary feature merges
are introduced. The diff against the shared parent is exactly the seven files
listed above; no secret, environment file, PDF, database or generated artifact
is part of the candidate. Syntax, lint, whitespace and added-line secret checks
passed. All original branches/worktrees and the empty stash list are preserved.

The baseline's deliberate partial email uniqueness produces Django `auth.W004`.
It is documented in `docs/qa/WORKSPACE_PORTAL_AUTH.md`: non-portal emails retain
case-insensitive uniqueness and portal principals bind by unique Google subject;
the natural-key manager excludes portal-only accounts. We did not suppress the
warning or change authentication. System checks report this warning, and migration
drift checks report no changes. The new existing team migration
`backend/apps/accounts/migrations/0009_workspace_portal.py` was exercised only in
disposable databases. Deployment of that baseline migration requires the normal
separate database rollout; these acceptance fixes introduce no migration.

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
- `/tmp/btu-final-latest-20261029.log`
- `/tmp/btu-final-latest-frontend-20261029.log`
- `/tmp/btu-final-portal-ui-20261029.log`
- `/tmp/btu-final-after-ui-20261029.log`

The environment injects `.git` markers above ordinary writable temp roots;
credential protections correctly reject files under those roots. Disposable
backend fixtures run in `/dev/shm` outside Git with execution permission. No
credential guard was bypassed. The earlier missing-artifact-directory invocation
was corrected by supplying `BTU_TEST_ARTIFACTS`, without changing application code.

## Integration and remaining scope

**READY FOR INTEGRATION against 64a1cd5.** Final isolated candidate branch:
`integration-candidate/all-dev2-20261029`, retaining the existing isolated
worktree and all tested changes. The commit containing the completed final report
is the delivery candidate. Resolve its full
hash with `git log -1 --format=%H -- ops/FINAL_ACCEPTANCE_REGRESSION_2026-10-29.md`.
The latest user instruction explicitly authorizes normal integration and push.
No force push or shared-history rewrite is needed.

The final fetch must confirm the tested shared parent before integration. If it
advances, do not force or treat this evidence as covering new code. The local
integration branch is unused by other worktrees and can be fast-forwarded in
this owned clean worktree. Only the existing integration branch is pushed.

```sh
git fetch origin
git switch integration
git merge --ff-only integration-candidate/all-dev2-20261029
git push origin refs/heads/integration:refs/heads/integration
git fetch origin refs/heads/integration:refs/remotes/origin/integration
git rev-parse HEAD origin/integration
```

No shared Neon migrations are necessary for these corrections. Existing baseline
migrations remain a separate deployment responsibility.

This task does not implement the Skills Gap Analyzer UI, redesign the website or
prove real BTU endorsement. Public Amoy, real Google Sheets/OAuth, real Classroom,
SMTP, Chrome-extension acceptance and deployed hosting remain externally untested.
Synthetic local services and real Anvil transactions do not establish those claims.
Shared `main` is outside the integration operation; its pre-operation hash is
46c8e56ac5fe761b391f70f842e22d0b176736bc. Exact final remote SHA and preservation
checks are provided in the final response and an outside-Git delivery receipt.
