# Lizi blockchain integration candidate, October 28

Review candidate only. No push, shared integration/main merge, persistent database
migration, Google API access, public transaction or Amoy deployment is authorized
or performed by this integration. Local evidence is recorded separately below.

## Git baseline and scope

- Verified shared integration: `6ddd218c1bd1cc94853f59feafa723fb23aae72e`.
- Latest pushed Lizi branch: `origin/feature/passport-blockchain-proof`,
  `bf8508d9cc487125efc01d8cda5f3ccb9d992383`. Its parent is exactly the shared
  integration baseline. The sole additional commit adds repeatable local browser
  acceptance. Earlier `71be42d` contract correction and `dc6da57` independent
  Anvil acceptance are already ancestors of shared integration.
- Latest integrated Sopio source: `95861f1`; subsequent integration frontend
  adjustment: `66374a9`. Sopio's newer pushed `2199a37` is not on shared
  integration. The separately tested local frontend candidate `f14d2cb` is
  preserved and excluded from this blockchain-only merge.
- Reviewed spreadsheet integration `244996b` is already present. The newer Google
  Sheets backend feature `22aeaa4` is not integrated and remains separate. Existing
  Google provider/import fixtures are tested without real API access or keys.
- Candidate: `integration-candidate/lizi-blockchain-20261028`, in
  `AI-Passport-lizi-blockchain-20261028`, created from verified shared integration.
  No upstream is configured. Existing worktrees, branches, stashes and developer
  edits are preserved. New remote references were fetched without moving local
  developer branches.

## Reviewed implementation

The existing registry has issuer-only anchoring, terminal revocation/replacement,
duplicate document protection and delayed administrator rotation. Salted opaque
commitments preserve immutable document history without publishing student data.
The earlier zero replacement destination fix is already integrated. Its pinned
runtime intentionally rejects older deployments; this candidate does not change
the runtime or authorize migration of any existing registry/history.

Django already reserves per-signer nonces under PostgreSQL locks, persists signed
bytes and deterministic hashes before broadcast, retries unchanged transactions,
and verifies canonical receipts, transaction fields, emitted events, stored
commitments, current lifecycle, issuer trust and required confirmations. RPC
outage/reorganization cannot inherit a positive saved database status. Bounded
RPC reads and shared request budgets remain intact. Consumed/stuck nonces require
operator review; this candidate adds no fee replacement or nonce reset behavior.

The new commit adds `ops/test_live_browser_e2e.py`, extends
`ops/run_isolated_tests.py` with `--browser-http` / `--ui-http`, and includes
Lizi's original local acceptance report. The new graphical harness uses real OTP,
sessions, CSRF, stored PDF bytes, a disposable PostgreSQL database, fresh local
Anvil signing accounts and three actual confirmations. Demo Mode is off. Private
fixture credentials and media are removed; only synthetic screenshots and
sanitized result JSON survive for review. Existing full-suite behavior is kept.

There are no new runtime features, security policy changes, API/ABI changes,
dependencies, migrations, frontend modifications, spreadsheet format changes or
merge conflicts. `blockchain/API_CONTRACT.md` is unchanged. Student/private PDF,
public verification, Admin permissions and reviewed import contracts remain the
existing interfaces. No change is required from Sopio for this commit.

Git merge-tree simulation also succeeds separately against local Sopio candidate
`f14d2cb` and Google feature `22aeaa4`. This is conflict evidence, not a claim that
those unmerged combinations received full runtime acceptance in this task.

## Reproduction

Run from the candidate root with installed locked dependencies. On this Windows
machine the Python executable is
`../.blockchain-stabilization-20261027/venv/Scripts/python.exe`.

```powershell
$env:PASSPORT_PG_BIN = 'C:\Program Files\PostgreSQL\18\bin'
$env:PASSPORT_ANVIL_BIN = "$PWD\blockchain\node_modules\@foundry-rs\anvil-win32-amd64\bin\anvil.exe"
$env:BTU_BROWSER_TOOLS = 'C:\Users\User\sth\AI-Passport\frontend-integration-20261028\browser-tools'
$env:BTU_BROWSER_EXECUTABLE = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
& ../.blockchain-stabilization-20261027/venv/Scripts/python.exe -B ops/run_isolated_tests.py --full --spreadsheet --browser-http
node blockchain/scripts/compile.mjs --check
node blockchain/scripts/test.mjs
```

Locked npm packages were installed separately in `frontend` and `blockchain`:

```text
npm.cmd ci --offline --ignore-scripts --no-audit --no-fund --cache C:/Users/User/sth/AI-Passport/audit-npm-cache-online
```

From `frontend`, run `npm.cmd run` for each of: `build`, `lint`,
`check:architecture`, `check:integration`, `check:auth`, `check:student`,
`check:verification`, `check:spreadsheet`, `check:admin`, `check:passport`,
`check:passport-card`, `check:demo`, `check:preview`. The last two use the process
environment `VITE_ENABLE_DEMO=true`; the real HTTP/browser harness explicitly
forces Demo Mode off. No environment file or live authentication setting changes.

## Fresh candidate results

All selected commands completed successfully on this Windows candidate.

| Gate | Fresh result |
| --- | --- |
| Solidity 0.8.30 compilation and complete committed artifact comparison | Passed; exact ABI/bytecode/runtime match |
| Solidity unit suite | 12 passed, 0 failed, 0 skipped |
| Disposable-resource guards | 6 tests plus 3 PostgreSQL interruption/refusal tests passed |
| Django system / migration drift | No issues / no changes detected |
| Focused spreadsheet mapping and migration suite | 38 passed |
| Spreadsheet socket HTTP | 13 real requests passed |
| Nine-app Django regression suite | 611 passed in 424.945 seconds; 613 discovered, two inherited exclusions listed below |
| Real HTTP/PostgreSQL/Anvil lifecycle | All 11 journeys passed; three required confirmations; five separate-client proof checks |
| Public verification UI/Django HTTP | 35 real proxied requests passed; jsdom driver |
| Student UI/Django HTTP | 65 real proxied requests passed; jsdom driver |
| Admin/Student/public UI/Django HTTP | 143 real proxied requests passed; jsdom driver |
| Native Chrome/Django/PostgreSQL/Anvil | 5 journey groups, 7 viewports, 75 actual API responses; mockedResponses=false |
| Frontend TypeScript/production build, lint and all 11 selected check scripts | Passed; 13 npm commands total |
| Changed-file whitespace / credential patterns / scope | Passed; no application, dependency, contract, spreadsheet or migration changes |
| Resource cleanup and developer preservation | Passed; outer cluster removed, private fixture/mail/media/signer/server/Vite cleaned; 14 original worktrees, 18 original branches, both stashes and existing developer edit preserved |

The existing runner excludes these two historical reference-SQL tests; they were
not executed or counted as passed. This integration adds no exclusions or skips:

```text
apps.skills.tests.SkillPostgreSQLTests.test_reference_schema_matches_migration
apps.students.tests.StudentPostgreSQLTests.test_reference_schema_matches_migration_and_preserves_foreign_keys
```

The chain HTTP test independently observed the new local registry deployment,
matched its exact runtime, checked its separate administrator and issuer role,
and recomputed salted PDF/snapshot commitments from a separate RPC client. Its
journeys exercised authorized synthetic Excel issuance into PostgreSQL, immutable
Passport versions and registered PDF bytes, original/tampered verification,
credential revocation, permissioned legal correction/replacement, confirmed
old-key cancellation dependency, historical Admin PDF access, terminal Passport
revocation, replay/deduplication and RPC connection failure/recovery retaining
saved hashes/nonces. No positive result was fabricated during the outage.

The graphical fixture exercised real OTP/session restoration, a backend-confirmed
Local Anvil badge, exact current and historical PDF downloads, current sharing,
public anonymous reference/PDF verification, preserved Student/Admin routes,
responsive navigation and secure logout. No API responses were intercepted.
Revocation/replacement/outage mutations are covered by the separate real HTTP
driver, while frontend contract fixtures cover their display states; this report
does not claim those mutations were clicked through in Chrome.

Viewports were 1440x900, 1366x768, 1280x720, 1024x768, 768x1024, 390x844 and
375x667, measuring all four Passport sections. Desktop and mobile screenshots
were also visually inspected. The mobile image includes a transient registered
PDF status query; the actual current/historical downloads passed earlier in the
same graphical journey.

Evidence is retained outside Git in
`C:/Users/User/sth/AI-Passport/blockchain-integration-20261028/`: full-acceptance.log,
solidity.log, frontend-checks-final.log, anvil-evidence.json, browser-review/,
preservation-after.json and before/after Git/listener inventories. The final local
merge SHA is recorded in that directory's DELIVERY.json and FINAL_REPORT.md.
No private fixture credentials, keys or PDFs were copied into browser-review.

## Issues and recommendation

- Critical: none demonstrated by this candidate review and acceptance.
- High: none demonstrated.
- Medium: none demonstrated within this integration scope.
- Low: inherited main frontend bundle exceeds Vite's 500 kB advisory; jsdom
  scripts emit React act advisories; deliberately throttled public uploads produce
  nonfatal Vite ECONNRESET diagnostics while the asserted 429 behavior passes.
  The two inherited reference-SQL exclusions above remain a coverage limitation.
- External dependency: Amoy, live Google/institutional services and the separate
  unpublished/unmerged work described below. None is claimed accepted locally.

An initial PowerShell frontend wrapper stopped when a successful build emitted
its chunk-size warning to stderr. The complete final frontend run used native
exit codes and all 13 commands passed; no assertion or timeout was weakened.
Deliberately induced domain-failure messages in regression logs are expected
failure-path coverage, not failing test results.

**Recommendation: Ready with noncritical limitations for review and a later
authorized merge into shared integration.** This is a tested local merge candidate,
not deployment approval or a combined acceptance of the separate Sopio/Google
feature candidates. No critical tests failed. No push or shared merge occurred.

## Remaining external gates

Public Amoy is untested and undeployed by this task. The policy supports only
approved local chains and HTTPS Amoy 80002, validates the pinned runtime and
injects Polygon PoA normalization. The suite includes a local Anvil chain-80002
envelope rehearsal; that does not contact Polygon or establish public RPC/fee
compatibility. Public readiness requires separate approval, review of any
unpublished Amoy preparation work, a real approved HTTPS RPC, funded dedicated
signer and separate administrator custody/ACLs, deployed registry/runtime/roles,
reviewed worker/nonce operations, history transition and public receipt acceptance.
No Anvil key is suitable for reuse on Amoy.

Live Google Sheets remains deferred by explicit user instruction. Its newer
feature branch and the newer Sopio candidate require separate integration review.
Persistent Windows/staging migration, institutional provisioning, hosted services,
SMTP and Classroom acceptance are outside the local results. Gap Analyzer UI is
still Coming Soon; it is not changed or claimed complete here.
