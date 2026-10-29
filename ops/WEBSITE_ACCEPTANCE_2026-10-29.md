# Isolated website acceptance — 2026-10-29

Historical initial-run report. See `FINAL_ACCEPTANCE_REGRESSION_2026-10-29.md`
for the subsequent complete backend rerun, refined storage recovery and final
integration candidate status.

Repository: https://github.com/samkharadzesopio/AI-Skills-Digital-Passport

## Source and preservation

Fetched `origin --prune`, then explicitly fetched all remote heads because the
checkout's configured fetch refspec only covered main. No configuration was changed.
Selected the preferred shared baseline `origin/integration` at
`319449d53825c6bc888b7c780130ee8eb320a534`, rather than main (`46c8e56`).
No newer team-designated integration baseline was provided.

Created branch `test/full-website-acceptance-20261029` and worktree
`/workspace/AI-Passport-website-acceptance-20261029` from that exact commit.
The original worktree remains on `feature/passport-blockchain-proof` at `858e1b7`.
It was clean, had no untracked files, and there were no stashes. Existing local
branches were retained. No feature branches were merged into the testing branch.

Included sources:

- Latest frontend/backend path changes: `d208cdd` (Google Student sign-in),
  merged through `319449d`.
- Reviewed Admin/frontend source `2199a37`, reviewed Sheets source `22aeaa4`,
  and blockchain/verification heading correction `858e1b7` are ancestors.
- Blockchain contract audit merge `865877d`, runtime implementation including
  `dcd0da4`, and local tooling `496d2a7` are integrated.
- Immutable PDF/automatic-award changes `2524109` are integrated.
- Existing renderer is `backend/passport_pdf_renderer.py`; it was not replaced.

Student/Admin APIs, public verification, accounts, Passport lifecycle, PDF storage,
Excel imports, bounded Google Sheets sources, deterministic recommendations and
local Anvil/Amoy configuration code are present. Older frontend feature refs
`a1c531c`, `fa30674`, `adb4dee` and `565d2c1` are not all Git ancestors of this
baseline; they were not silently merged. The shared reviewed implementation is
the test target. Unpushed teammate files on other machines cannot be inspected.

## Reproduced failures and corrections

1. Full regression: 673 executed, 671 passed, two failed. Both failures were
   investigated without removing assertions:
   - `test_changed_storage_bytes_are_not_anchored`: the newer immutable-PDF
     service raises ValidationError before opening corrupt bytes. The worker
     classified that as transient. It now records terminal PDF_STORAGE_MISMATCH
     before signing instead of retrying the integrity rejection.
   - `test_parallel_different_documents_reserve_distinct_nonces`: renderer
     changes now correctly reuse the immutable issued document. The test now
     publishes a genuinely different academic snapshot and asserts distinct
     document IDs before checking concurrent nonce allocation.
2. Public HTTP expired fixture used today's earned date with issuance three days
   earlier. The authoritative-date rule correctly rejected it. Freeze the fixture
   clock at historical issuance; preserve the production date rule and verdicts.
3. Added `--blockchain-regression` to the disposable runner for a full focused
   blockchain rerun. No migration, dependency lock, contract artifact or frontend
   layout changes were needed.

## Executed gates

- Solidity 0.8.30 artifact comparison passed; all 12 Foundry tests passed.
- All 14 frontend npm gates passed: build, lint, architecture, integration, auth,
  Student, verification, spreadsheet, Admin, Passport, Passport card, demo,
  preview and Passport layout. Seven viewports and all 33 variable-content pages
  passed layout checks. Build retains its chunk-size advisory.
- Two additional Admin visual checks passed: 32 page/viewport cases and actual
  XLSX parsing/invalid-file cleanup/disabled submission. These use synthetic UI
  fixtures, not live provider acceptance.
- Google approval guards 4; disposable-resource guards 10; local profile checks
  3; Google-auth configuration guards 4: passed.
- All 107 account tests passed; Google-auth Chrome/Django: five groups and 49
  actual API responses passed, with synthetic GIS/keys and no live Google.
- Issued-artifact no-regeneration test passed. Automatic award -> PDF -> Anvil
  acceptance passed, including immutable old artifacts and tamper rejection.
- Integrated import Chrome/Django: seven groups, 91 actual API responses passed.
- Focused spreadsheet/configuration/preflight: 50 passed; Excel socket HTTP:
  13 requests passed. Synthetic Google Sheets: 25 real local HTTP requests passed,
  including independently checked Anvil proof. No real Google API was called.
- After correction, all 101 Django blockchain tests passed in 156.893 seconds.
- All 11 HTTP/Anvil lifecycle journeys passed, including three confirmations,
  separate-client proof checks, cancellation dependency, revocation, replay,
  permission denial, privacy, RPC outage and worker recovery.
- Corrected public HTTP suite passed 35 proxied requests, including real 429,
  anonymous uploads and private API denial; jsdom driver, not graphical Chrome.

- Student UI/HTTP: 65 real requests passed, including OTP, restoration, logout,
  ownership denial and CSRF. Admin/Student/public UI/HTTP: 148 real requests
  passed, including import recovery, replay, issuance and revoked PDF verdicts.
- Final graphical Chrome/Django: six journeys, seven viewports, 95 actual API
  responses passed. All owned database, server, Vite, Anvil, signer, mailbox and
  fixture resources were removed. No unresolved failing test remains in the
  affected reruns. jsdom HTTP tests emit React act() advisory warnings.

The full 673-test suite has not been rerun after the scoped
fixes; the entire affected blockchain app was rerun instead. Two inherited legacy
reference-SQL tests are excluded by the existing runner and are not counted as
passed: StudentPostgreSQLTests.test_reference_schema_matches_migration_and_preserves_foreign_keys
and SkillPostgreSQLTests.test_reference_schema_matches_migration.

## Reproduction and evidence

Dependencies installed from both npm lockfiles. Python uses the existing
`.venv-auth` interpreter, PostgreSQL 17 local binaries, native Anvil, Chromium and
separate Playwright tools. This environment places synthetic `.git` markers above
ordinary writable temp directories. The credential guard correctly refused them;
isolated execution used `/dev/shm` outside Git, without weakening the guard.
The automatic-Passport driver requires an explicit `BTU_TEST_ARTIFACTS` directory;
the first attempt without it stopped, then was rerun with that configuration.

Commands use these environment values (adapt executable paths on other machines):

```sh
export TMPDIR=/dev/shm
export PASSPORT_PG_BIN=/tmp/btu-phase1-tools/pg-bin
export BTU_BROWSER_TOOLS=/tmp/btu-live-browser-tools
export BTU_BROWSER_EXECUTABLE=/usr/bin/chromium
export BTU_TEST_ARTIFACTS=/tmp/NEW_OWNED_ARTIFACT_DIRECTORY
python -B ops/run_isolated_tests.py --full --spreadsheet --google-sheet --frontend-browser --browser-http --google-auth --google-auth-browser --automatic-passport
python -B ops/run_isolated_tests.py --blockchain-regression --ui-http --browser-http
```

Logs outside Git: `/tmp/btu-acceptance-20261029.log`,
`/tmp/btu-acceptance-main-20261029.log`, `/tmp/btu-acceptance-blockchain-20261029.log`,
`/tmp/btu-acceptance-ui-20261029.log`, `/tmp/btu-frontend-acceptance-20261029.log`,
`/tmp/btu-admin-ux-20261029.log`. Synthetic artifacts remain outside Git.

## Limits and delivery

The separate Full Website Phase 1–13 prompt was not supplied in this task.
This report covers repository-provided automated gates, not an assertion that
unspecified phase requirements or all product features are complete.
Student Skills Gap Analyzer still displays Coming Soon despite an existing
deterministic recommendation backend. Real Classroom, real Google Sheets/OAuth,
SMTP delivery, Chrome-extension acceptance, hosting and public Polygon Amoy were
not tested. Synthetic institutional configuration is not real BTU endorsement.

No shared Neon migration, persistent developer database change, public blockchain
transaction, push or merge was performed. Corrections remain local for review.
Both the final HTTP/browser runner and the focused 101-test blockchain stage
passed after the scoped fixes. This is a tested integration candidate, not a
claim of public-provider readiness or completion of every product requirement.
