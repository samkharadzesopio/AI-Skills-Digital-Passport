# Functional audit stage reports

## Stage 1 — Environment and repository readiness

- Approved baseline and clean feature HEAD: `b2e916af0221e35bddb0a5db19c0379cc45d6923`.
- Branch: `feature/fullstack-agent-fixes`; worktree: `C:/Users/User/sth/AI-Passport/AI-Passport-fullstack-agent-fixes`.
- Refreshed remote refs without changing working files/local branches. Remote integration matches baseline; remote main is `46c8e56ac5fe761b391f70f842e22d0b176736bc`. No remote Google-student-auth branch or audit feature branch was advertised at this check.
- Installed Python 3.13.13, Django 6.1.2, DRF 3.18.3, psycopg 3.3.6, Web3 7.13.0, PyMuPDF 1.28.2, openpyxl 3.1.5 and gspread 6.2.1. Node 26.3.0, npm 11.16.0, PostgreSQL 18.6.
- Frontend lockfile: React 19.3.1, Vite 8.3.5 and TypeScript 6.0.3. Fresh checkout dependencies not installed yet.
- Chrome and separate Playwright installation exist. The documented Python interpreter requires sandbox escalation to access its base executable; the read-only version check succeeded.
- Tests will create a fresh PostgreSQL cluster and unique owned databases through `ops/run_isolated_tests.py`/`DisposableRun`. No existing databases or servers will be adopted. Existing listener inventory includes PostgreSQL 5432, previews 5173/5174/5175/5176/5178 and backend 8003; these are preserved.
- Five specialist roles run in waves with no more than three active specialists. Detached task-owned worktrees hold proposed patches; only the coordinator may commit/push, only on the approved feature branch.
- Source requirements: the owner's comprehensive prompt and mandatory addendum are primary acceptance criteria. No separate official rubric was found in tracked files; existing reports are historical evidence. `backend/data/students.xlsx` is not opened or used as test data.
- No audit test results or application repairs exist yet. Next: enumerate routes and distinct controls, establish intent and identify decision checkpoints.

Evidence directory outside Git: `C:/Users/User/sth/AI-Passport/fullstack-agent-audit-20261028/`. User instructions, baseline refs/worktrees/stashes and listener inventory are preserved there. Original setup snapshots remain in `../fullstack-agent-setup-20261028/`.

## Stage 2 — Source route/control inventory

Measured 48 React route patterns: 30 view routes, 14 redirects and 4 fallbacks. This is not a unique-component count. Source inventory has 401 distinct existing control-action records: 344 frontend (105 Demo, 175 Live, 64 shared) and 57 imports (23 Demo, 34 Live). Repeated labels with distinct actions/context have separate IDs. Classroom UI is F-owned; imports semantics are I-owned, avoiding duplicate UI counts. All runtime outcomes remain pending until execution evidence is attached.

Separate backend matrices map 28 private method/action contracts across 26 paths, plus nine PDF actions. Three lifecycle contracts are delegated by reference, not counted twice. Live catalog/mapping writes, generalized security-audit reading and the career Gap Analyzer are explicitly unsupported/disabled; no policy or functionality is invented. Authentication controls are read-only audit/handoff scope.

Required new-source discovery is missing. Owner approved PD-01/PD-01a: controlled source-level automation, existing permitted accountable admin, no student opt-in additions, CONFIRMED-only, disable/revocation, manual imports retained, synthetic tests only. Existing profile/source/issuer/institutional-reference requirements remain prerequisites. Legal processing permission is not established by administrator approval. No merge or push is authorized pending a further owner decision.

## Stage 3 — Initial testing, first checkpoint

Initial aggregate command: `ops/run_isolated_tests.py --backend --spreadsheet --google-sheet --frontend-browser --browser-http`. The runner executes frontend browser mode before backend. It failed at `frontend/scripts/check-frontend-django-http.mjs:159`: Student PDF generation logged `Private passport PDF generation unavailable.` and native Chrome timed out waiting for download. Exact application root cause is under investigation; classify P1 required-PDF candidate, not yet repaired. Later aggregate stages did not execute and are not passed.

Current passed checks: four Google-access gate checks, six owned-resource cleanup tests, three PostgreSQL failure/interruption cleanup tests, Django system checks and no migration drift. Separate pinned compiler/artifact comparison and all 12 Solidity tests passed (zero failures/skips). No current full backend result yet. Owned initial cluster cleanup succeeded after browser failure. Log: `initial/baseline.log`; two sanitized Admin import screenshots survived before failure. No screenshots establish complete control coverage.

Passport specialist is reproducing the underlying generation exception; independent QA is creating per-control actual-browser evidence with isolated failures and untested rows explicitly separated. Backend regression will run separately so a frontend failure cannot suppress its evidence. No application fixes have been integrated.

## Stage 4 — Essential repairs completed

Owner resource directive replaced exhaustive secondary UI testing with essential repairs and targeted verification. Applied reviewed patches to the feature worktree by ordinary patch/file edits; no Git merge. Automatic sync passed 73 distinct targeted PostgreSQL tests and four native Chrome journey groups/36 page API responses. PDF work had 65 passing checks in the initial focused run; the only remaining assertion expected superseded renderer-regeneration behavior and was updated to the approved stronger immutable-reuse rule. All 12 affected date/font/API retests passed. Six corrected Georgian PDFs were rendered/inspected; neutral wording, earned dates and card bounds verified. Minimal already-completed Dialog fix passed seven focused native Chrome checks. Authentication and contracts untouched.

## Stage 5 — Final focused acceptance passed

Assembled candidate: `ops/run_isolated_tests.py --automatic-passport`, exit0. Latest missing/corrupt generation/private-open regression passed. One real synthetic-provider poll -> same Passport ID/first issuance -> new frozen version/PDF -> confirmed local Anvil -> independent receipt/commitment -> HTTP original VALID and altered not VALID -> historical bytes/hash/snapshot/proof preservation -> disable flow passed. Actual registered PDF cover/supplement visually inspected. Owned PostgreSQL/Anvil/server/media/signer/temp cleanup passed. Integrated frontend build/lint passed. Compact sanitized evidence is in `docs/qa/evidence/`.

The complete backend suite and all401 controls were not rerun; the owner explicitly prioritized resources. Initial browser wave exercised203 existing IDs, including harness failures, and198 remained unexercised. Existing login/public browser evidence is reused where code is unchanged. No full coverage, live Google, public-chain or production readiness claim.

## Stage 6 — Local delivery

Reviewed41-file candidate is saved as a local commit on `feature/fullstack-agent-fixes`, directly descended from the approved baseline. Exact commit SHA is available from `git rev-parse HEAD` and external `fullstack-agent-audit-20261028/DELIVERY.json`. Normal feature-branch push remains subject to explicit owner approval. No Git merge, push or deployment performed.

Protected remote heads were rechecked: integration remains `b2e916af0221e35bddb0a5db19c0379cc45d6923`, main remains `46c8e56ac5fe761b391f70f842e22d0b176736bc`. Original16 worktree heads/statuses, two auth stashes and the original PDF report edit were preserved. No authentication, smart contract, dependency-lock or production configuration source changed. Added-line credential-pattern and whitespace checks passed; these scans do not prove live credential safety.

Remaining work is in REMAINING_WORK.md and HANDOFF.md:198 secondary IDs, lower-priority candidates, full regression, separate Google-auth compatibility and external/institutional/deployment gates. No confirmed critical blocker remains within the focused locally tested priority flow.
