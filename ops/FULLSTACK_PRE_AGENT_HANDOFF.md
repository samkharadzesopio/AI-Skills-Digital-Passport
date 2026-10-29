# Full-stack baseline before the separate functional audit

## Version and delivery identity

Combined merge: `4e289e682b2f6ea01457e6ee9209672e89845df7`.
Application/test source baseline: `8590f9dff76a5738b60d03efe92d944308e01edb`.
The latter adds only two browser-label corrections to the third controlled merge;
it changes no application runtime. Both include all sources below. The delivery
commit also contains this handoff; resolve its exact SHA with
`git log -1 --format=%H -- ops/FULLSTACK_PRE_AGENT_HANDOFF.md`. After the authorized
push, `git rev-parse origin/integration` identifies the delivered shared head.
The exact delivery SHA, push verification and full report are also recorded in
`../fullstack-pre-agent-20261028/DELIVERY.json` and `FINAL_REPORT.md` on the
integration machine. A checkout's `git rev-parse HEAD` is its reproducible version.

| Source | Exact included commit |
| --- | --- |
| Starting shared integration | `6ddd218c1bd1cc94853f59feafa723fb23aae72e` |
| Sopio original frontend | `2199a3727a2675097121c7a45326a7f83cac9e98` |
| Reviewed Sopio/Django candidate | `f14d2cb86832b05bdc9d18b275a280df879b810f` |
| Google Sheets backend feature | `22aeaa4129b536fa001d2d392564244200bac978` |
| Lizi original pushed source | `bf8508d9cc487125efc01d8cda5f3ccb9d992383` |
| Reviewed Lizi candidate | `caf58b6bb539af4c12c7240ef4fd13e7984bc7bf` |

Candidate branch: `integration-candidate/fullstack-pre-agent-20261028`.
Worktree: `C:/Users/User/sth/AI-Passport/AI-Passport-fullstack-pre-agent-20261028`.
The three candidates were merged in the table's frontend, Google, Lizi order.
Original feature branches were not merged again. The shared test runner combines
all three flag sets without discarding any implementation; no text conflicts or
manual conflict resolutions were required.

Combined browser acceptance exposed two stale headings in Lizi's existing
`frontend/scripts/check-passport-browser.mjs`: `Skill catalog` and
`Approved course mappings`. The catalog API returned 200, but the old text lookup
timed out. The driver now asserts Sopio's existing `Skills Catalog` and
`Activity-to-Skill Mapping` labels. No application page, assertion, timeout or
security rule was removed/weakened. The complete affected Chrome/Anvil harness
passed on fresh owned resources. The initial failure is retained in the report.

Earlier source-specific reports retain their historical branch results and
unmerged-source notes. This handoff supersedes those integration-status notes;
their external-access and institutional-approval restrictions still apply.

Installed validation versions: Python 3.13.13, PostgreSQL 18.6, Django 6.1.2,
Django REST Framework 3.18.3, psycopg 3.3.6, Web3 7.13.0, gspread 6.2.1,
requests 2.34.2, PyMuPDF 1.28.2, openpyxl 3.1.5,
React 19.3.1, Vite 8.3.5, TypeScript 6.0.3, Foundry/Anvil 1.7.1,
Solidity 0.8.30, OpenZeppelin 5.4.0, optimizer 200, Cancun EVM.
Keep both npm lockfiles and the pinned Python requirements.

## Acceptance status

All mandatory gates ultimately passed on the actual combined application.
The first aggregate command exited 1 at the stale-heading browser failure after
all its preceding stages passed. The targeted complete browser rerun exited 0
after the two-label correction. No application code changed between those runs;
the earlier backend/build/contract results still cover the identical runtime.
There are no unresolved failing mandatory tests, and no failure was skipped.

| Gate | Fresh combined-source result |
| --- | --- |
| Django system / migration drift | No issues / no changes detected |
| Full nine-app backend regression | 619 passed in 608.565 seconds; 621 discovered, two inherited exclusions below |
| Focused spreadsheet/configuration/preflight suite | 50 passed; overlaps the full suite |
| Google approval/resource cleanup guards | 4 + 6 + 3 passed; repeated successfully for the browser rerun |
| Excel socket HTTP | 13 real requests passed |
| Synthetic Google provider + HTTP/PostgreSQL/PDF/Anvil | 25 real local HTTP requests passed; no real Google calls/keys |
| Solidity compiler/artifact | Solidity 0.8.30 compile passed; exact ABI/bytecode/runtime comparison passed |
| Solidity unit suite | 12 passed, 0 failed, 0 skipped |
| Real HTTP/Anvil lifecycle | All 11 journeys passed; 3 confirmations and 5 separate-client proof checks |
| Public UI/Django HTTP | 35 real proxied requests passed; jsdom |
| Student UI/Django HTTP | 66 real proxied requests passed; jsdom |
| Admin/Student/public UI/Django HTTP | 144 real proxied requests passed; jsdom |
| Native Chrome Admin/import/Student/public acceptance | 7 journey groups, 78 real API responses; Demo off, mockedResponses=false |
| Native Chrome confirmed Anvil acceptance, after correction | 5 journey groups, 7 live viewports, 78 actual API responses; mockedResponses=false |
| TypeScript/production build, lint and selected frontend checks | All 14 npm commands and 2 direct browser scripts passed |
| Graphical Passport stress fixtures | 7 viewport sizes, all 33 variable-content pages, no clipping/internal scroll |
| Graphical Admin/legacy-preview fixtures | 32 viewport/page checks; XLSX parsing/cleanup and blocked mutations passed |
| Diff/privacy review | No secret-pattern findings; no new migrations, dependency locks or contract/API artifacts |
| Owned cleanup / original developer work | Both test clusters removed; private fixtures/mail/media/signers/server/Vite cleaned; original worktrees/refs/stashes preserved |

The existing runner excludes these historical reference-SQL comparisons. They
were not executed or counted as passed; this integration adds no exclusion:

```text
apps.skills.tests.SkillPostgreSQLTests.test_reference_schema_matches_migration
apps.students.tests.StudentPostgreSQLTests.test_reference_schema_matches_migration_and_preserves_foreign_keys
```

Real HTTP journeys include authorized issuance, immutable versions, registered
PDF bytes, original/tampered verification, credential revocation, permissioned
legal correction/replacement and old-key cancellation dependency, terminal
Passport revocation, idempotency, nonce/hash retention and truthful RPC outage
recovery. The separate Chrome tests cover official award preview/confirmation
and known/unknown/original/modified evidence, as well as actual confirmed local
proof and responsive Student/Admin/public navigation. Mutation/outage scenarios
are exercised by the HTTP driver; they are not claimed clicked through in Chrome.

Review artifacts and exact command logs are outside Git at
`C:/Users/User/sth/AI-Passport/fullstack-pre-agent-20261028/`:
`full-acceptance.log`, `browser-rerun.log`, `frontend-checks.log`, `solidity.log`,
`native-browser/`, `chain-browser/`, `browser-first-failure/`,
`anvil-evidence.json`, Git/listener inventories, `FINAL_REPORT.md` and
`DELIVERY.json`. Screenshots contain synthetic records only. Private keys, OTPs,
passwords and PDFs are not retained in browser review artifacts. The existing
source reports are historical evidence, not substitutes for these fresh results.

## Compatibility and institutional boundaries

React preserves Student landing/Passport presentation, grouped Admin navigation,
dashboard, directory, catalog, course mapping, credentials, Imports & History,
public verification and responsive layouts. Sessions, CSRF and Student ownership
remain server enforced. No login bypass was added to Live Mode.

Google changes retain existing profile/preview/confirmation DTOs and add bounded
server-configured A1 ranges, outside-Git credential path safeguards, read-only
scopes, bounded retries/timeouts, session closure and preflight diagnostics.
`--full` never selects real Google. Both explicit live flags and separate owner
approval remain necessary for any future Google acceptance. No real key is needed
for the synthetic provider tests.

The three conceptual registers are Students, Skills Catalog and Verified Skills.
Student ID and Skill ID link approved awards; Record ID provides deduplication.
CONFIRMED evidence still requires the authorized source/profile/administrator
workflow. PENDING, REJECTED, unknown students/skills, formulas and conflicting
records cannot issue credentials. Replays preserve the permanent Passport ID,
achievements and immutable version history.

The BTU 20-column workbook and three-register specification are distinct formats.
The source workbook's Passport Sync Status and other synchronization outputs do
not establish institutional approval. Existing profiles reject those outputs as
approval aliases. Synthetic browser fixtures preserve the 20-column shape and
show zero eligible awards without independent approval; a separate synthetic
approved format demonstrates legitimate issuance. No real records are imported
and no official workbook is rewritten. Real profile/source approval remains an
institutional dependency, not a failed merge to work around.

Blockchain business logic/API/contract artifacts are unchanged by these merges.
Read `blockchain/API_CONTRACT.md` for authoritative status mappings. Only current
ACTIVE, valid credentials with live confirmed proof and authorized institutional
issuer/signer can receive a positive badge. Pending, failed, unavailable and
unconfigured proof remain distinct; saved CONFIRMED rows do not override a live
RPC outage or cancelled identity. Local evidence is labeled Local Anvil.

The earlier pinned-runtime correction is already included. Existing older
registries deliberately fail the runtime check. Do not change an existing
database's registry address, rewrite proofs or reset nonces to make it appear
compatible. Persistent migration/registry history transitions need their reviewed
runbooks and separate approval. No new migration is added by this integration.

## Known issues and functional-audit backlog

| Priority / severity | Component | Known issue or limitation; next action |
| --- | --- | --- |
| P1 / Medium | Imports & History | Demo prominently presents the legacy local `student_id/course_id/skill_id` preview. Its notice says it cannot import/issue official records, but the workflow can still confuse users expecting the official workbook. Review mode/schema labeling and discovery in the next phase; preserve the approval boundary. |
| P1 / Medium | Live imports | `/admin/imports` renders server-reviewed awarded-skill profiles first, followed by explicitly described legacy completion-evidence controls and persisted history. Verify task-oriented navigation/access with actual grants; do not replace either parser or reinterpret formats. |
| P2 / Medium | Admin catalog/mappings | Live Add/Edit catalog/course mappings and generalized non-course activity writes lack approved backend write/policy APIs. Read workflows exist; disabled/unsupported writes must remain truthful until approved APIs are implemented. |
| P2 / Medium | General audit logs | No dedicated sanitized general security-audit read API/grant. Credential/import/sync-specific histories exist. Define scope and permissions before implementing new access. |
| P2 / Medium | Skills Gap Analyzer | Frontend remains Coming Soon. Backend deterministic course recommendations are separate; do not present fabricated AI output. |
| P2 / External | Classroom | Existing backend simulation is labeled SIMULATED. No institutional Classroom connector acceptance or automatic real ingestion is claimed. |
| P2 / External | Google Sheets | Synthetic-provider integration is implemented/testable. Real authentication, sharing, access, quota and live acceptance remain separately approved external gates. |
| P2 / External | Public blockchain | Amoy is undeployed/untested publicly by this work. Local success does not establish public RPC, custody, funding, fee or deployment readiness. |
| External observation | Existing local preview | The pre-existing backend on port 8003/PID 33564 was no longer listening after this long run. Its shutdown cause was not determined; no task command targeted it or adopted its database. PostgreSQL 5432 and previews 5178/5179/5180 retained their original listeners. Automated acceptance used its own random ports and cleaned them. |
| P3 / Low | Build/test tooling | Inherited main JS bundle exceeds 500 kB advisory; jsdom act advisories and proxy resets during asserted upload-throttling scenarios are tracked separately from failures. |
| P3 / Low | Historical SQL comparisons | Two inherited reference-SQL tests are excluded by the existing foundation runner; active migration and PostgreSQL checks still run. List exact exclusions below. |

No exhaustive every-button audit or broad functional repair is included here.
Student academic identity is intentionally university maintained and read-only;
arbitrary credential issuance and client-supplied issuer/network overrides are
intentionally prohibited, not controls to enable during debugging.

## Demo Mode and Live Mode

- Demo is development-server-only: `VITE_ENABLE_DEMO=true` plus Vite serve.
  It uses synthetic previews, skips real login and blocks official mutations and
  verification claims. Production build/preview force Demo off.
- Live uses `VITE_ENABLE_DEMO=false`, Django Student OTP/Admin password sessions,
  explicit grants, CSRF, authorized evidence, PostgreSQL and original stored PDF
  bytes. Missing providers/approvals yield honest unavailable states.
- Anvil is genuine local EVM evidence, not Demo mock proof and not public Amoy.
  The integrated acceptance uses three required confirmations and fresh keys.
- An already running local preview can still serve another worktree. Verify its
  process/root before claiming a URL is this integration. This task preserves
  existing servers instead of silently moving their source directories.

## Exact automated startup and test commands

From the candidate root on the integration machine:

```powershell
$python = 'C:\Users\User\sth\AI-Passport\.blockchain-stabilization-20261027\venv\Scripts\python.exe'
$env:PASSPORT_PG_BIN = 'C:\Program Files\PostgreSQL\18\bin'
$env:PASSPORT_ANVIL_BIN = "$PWD\blockchain\node_modules\@foundry-rs\anvil-win32-amd64\bin\anvil.exe"
$env:BTU_BROWSER_TOOLS = 'C:\Users\User\sth\AI-Passport\frontend-integration-20261028\browser-tools'
$env:BTU_BROWSER_EXECUTABLE = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$env:BTU_TEST_ARTIFACTS = 'C:\Users\User\sth\AI-Passport\fullstack-pre-agent-20261028\native-browser'
npm.cmd --prefix frontend ci --offline --ignore-scripts --no-audit --no-fund --cache C:/Users/User/sth/AI-Passport/audit-npm-cache-online
npm.cmd --prefix blockchain ci --offline --ignore-scripts --no-audit --no-fund --cache C:/Users/User/sth/AI-Passport/audit-npm-cache-online
node blockchain/scripts/compile.mjs --check
node blockchain/scripts/test.mjs
& $python -B ops/run_isolated_tests.py --full --spreadsheet --google-sheet --frontend-browser --browser-http
& $python -B ops/run_isolated_tests.py --browser-http
```

Each test command starts its own fresh loopback PostgreSQL, Django WSGI, React
Vite servers and Anvil deployments, runs acceptance, then stops/removes only its
owned resources. It never adopts a database or imports production `.env`. Use
this for a reproducible synthetic full-stack startup rather than pointing tests
at a running preview/shared database. Browser tool dependencies remain separate
from application npm dependencies. Do not pass either live Google flag.

Targeted existing modes: `--backend`, `--spreadsheet`, `--google-sheet`,
`--chain-http`, `--ui-http`, `--frontend-browser`, `--browser-http`.
Each invocation still runs resource guards and system/migration checks.

From `frontend`, execute `npm.cmd run` for each of `build`, `lint`,
`check:architecture`, `check:integration`, `check:auth`, `check:student`,
`check:verification`, `check:spreadsheet`, `check:admin`, `check:passport`,
`check:passport-card`, `check:demo`, `check:preview`, `check:passport-layout`.
Also run `node scripts/check-admin-ux.mjs` and
`node scripts/check-admin-import-preview.mjs`.
Set `VITE_ENABLE_DEMO=true` only for `check:preview`; other commands used false.
The latter import-preview check intercepts read-only synthetic API fixtures;
report it separately from real HTTP/browser acceptance.

To isolate graphical artifacts, this run sets `TEMP` and `TMP` to
`../fullstack-pre-agent-20261028/frontend-temp`, `BTU_TEST_ARTIFACTS` to its
`frontend-visual` directory, and `BTU_TEST_VITE_CACHE` to its
`frontend-vite-cache` directory for the frontend checks. Use a new owned artifact
directory for a new audit; do not overwrite another developer's evidence.

## Manual local services: after separate environment review

The disposable startup above is the tested way to launch the complete stack.
For a longer-lived manual environment, first review
`ops/BACKEND_ANVIL_LOCAL_RUNBOOK.md` and `ops/BACKEND_MIGRATION_RUNBOOK.md`.
No persistent database was provisioned, migrated or approved by this task.
The existing local profile requires DEBUG, explicit development activation and
loopback database `btu_passport_local`; it cannot adopt an arbitrary test database.

With an operator-owned cluster directory already identified (not a shared service):

```powershell
if (-not $env:BTU_OWNED_LOCAL_PGDATA) { throw 'Supply the reviewed owned local cluster directory.' }
& "$env:PASSPORT_PG_BIN\pg_ctl.exe" -D $env:BTU_OWNED_LOCAL_PGDATA -l "$env:BTU_OWNED_LOCAL_PGDATA\server.log" -o '-h 127.0.0.1 -p 55432' -w start
& .\blockchain\node_modules\@foundry-rs\anvil-win32-amd64\bin\anvil.exe --host 127.0.0.1 --port 8545 --chain-id 31337 --silent
```

Anvil runs in its own terminal. It does not deploy a registry. Institutional
issuer/admin configuration, a matching already-reviewed local registry and
fresh local-only signing custody must exist before the following Live commands.
Keep keys/OTP/mail/configuration outside Git; no Anvil key may be reused publicly.
Do not run a public deployment command as part of this handoff.

After separately reviewed local migrations/configuration, run in separate terminals:

```powershell
$env:BTU_LOCAL_DEVELOPMENT = '1'
$env:VITE_ENABLE_DEMO = 'false'
$env:BTU_DEV_API_TARGET = 'http://127.0.0.1:8000'
$env:PASSPORT_BLOCKCHAIN_CONFIRMATIONS = '3'
& $python backend/manage.py runserver 127.0.0.1:8000 --noreload --settings=config.local_dev_settings
& $python backend/manage.py run_backend_workers --settings=config.local_dev_settings
& $python backend/manage.py process_blockchain_proofs --watch --settings=config.local_dev_settings
npm.cmd --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

`ops/start_local.ps1 -Python $python` is the existing alternative Django/Vite
launcher; it refuses occupied default ports/pending migrations and starts neither
PostgreSQL, Anvil nor workers. Configure each terminal consistently. The Live
Student entry is `http://127.0.0.1:5173/student/login`; Demo direct entry is
`/student/dashboard` only when the local flag is explicitly true.

## Next phase

Start the separate functional audit from the delivered commit. Preserve this
baseline and use isolated branches/worktrees, synthetic resources and explicit
task ownership. Prioritize import-mode/schema clarity, actual approved workflow
discovery, capability-based controls and truthful unavailable states before
broader UX/feature repairs. Reproduce a reported bug before changing behavior and
rerun affected real HTTP/browser/Anvil tests. Institutional approval, live Google,
Classroom, SMTP, hosting and Amoy are external acceptance tasks, not gates that
synthetic fixtures can silently satisfy.
