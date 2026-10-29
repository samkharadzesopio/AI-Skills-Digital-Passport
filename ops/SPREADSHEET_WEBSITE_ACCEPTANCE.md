# Reviewed spreadsheet workflow in the website

Baseline: `96ec681b4ae75fd11875386e154e7b1208d04daf`. Backend feature:
`6ab0698fd4e16035e16eb3c7d7f145f0427d1475`. The feature merges additively;
no Student design, artwork, public verifier, blockchain contract or signer code
is replaced. Ongoing frontend and blockchain deployment branches are excluded.

The Live `/admin/imports` page retains strict completion imports and adds approved
profile selection, Excel or configured Google source preview, original header/
column positions, all row classifications, explicit confirmation of the exact
snapshot digest, outcome refresh and persisted import history. New skill-award
receipts recover through the saved preview, not the legacy completion-event retry
route. The history parser accepts both legacy `type` and reviewed-import `code`
errors. Backend permission, session, CSRF and preview ownership checks remain
authoritative. Private files and previews stay in memory and clear on account
changes/unmount. Errors use fixed messages; raw provider diagnostics are excluded.

The new integrations migrations `0003` and `0004` add profiles, immutable reviewed
snapshots and award receipts with protected history. Existing migrations are not
edited. Fresh install and populated pre-feature schema rehearsals compare every
pre-existing table, registered PDF bytes and signed Anvil history. Reversing the
history guard with reviewed imports is intentionally refused. Follow the
[migration runbook](SPREADSHEET_MIGRATION_RUNBOOK.md) before any persistent rollout.

## Repeatable checks

Use an environment containing the repository's Django/PostgreSQL/Web3 test
dependencies and local Anvil. Set `PASSPORT_ANVIL_BIN` when Anvil is not on PATH.
These commands create their own loopback PostgreSQL clusters; they must not adopt
existing databases or production settings:

```text
python -B ops/run_isolated_tests.py --full
python -B ops/run_isolated_tests.py --spreadsheet
cd frontend
npm ci
npm run build
npm run lint
npm run check:architecture
npm run check:admin
npm run check:verification
npm run check:demo
npm run check:passport
npm run check:auth
npm run check:student
npm run check:passport-card
npm run check:passport-layout
npm run check:integration
npm run check:spreadsheet
```

`check:preview` requires `VITE_ENABLE_DEMO=true`; it deliberately asserts that
the real Vite configuration enables Demo Mode and performs zero private API
requests. `check:passport-layout` uses an isolated Playwright installation supplied
through `BTU_BROWSER_TOOLS`, with `BTU_BROWSER_EXECUTABLE` for system Chrome.
Demo/DOM/contract fixture checks are synthetic frontend tests, not HTTP evidence.

## Local acceptance evidence, 2026-10-28

The separate local evidence directory `../spreadsheet-final-20261028` contains the
read-only Git snapshots, full command logs, owned preview supervisor, browser
driver, screenshots, workspace inventory and acceptance JSON. None of its database
files, credentials, media, caches or generated output belong in Git.

Chrome acceptance used React `127.0.0.1:5177` proxying real Django on `8002`, a
new disposable PostgreSQL cluster and real local Anvil chain `31337`. No API
responses were intercepted. The synthetic workbook has headers on row 4,
reordered aliases, ignored extra content and seven evidence rows: one eligible,
one duplicate, three invalid and two requiring institutional review. Preview
created no awards, credentials or versions. Explicit confirmation created exactly
one achievement, credential and issued Passport version. Existing durable workers
generated its PDF and confirmed its Anvil transaction. The Student signed in via
the real OTP/session flow, viewed the imported skill and downloaded bytes matching
the registered PDF. Anonymous reference/original PDF verification succeeded;
modified bytes returned `UNVERIFIABLE` with `authentic: false`. Repeat confirmation
returned the saved outcome and a new preview classified the award as already
imported. CSRF, digest, workbook-format, profile and read-only Admin denials were
also exercised over HTTP. The browser JSON records 53 actual API responses.

The focused gate passed 38 spreadsheet domain/migration tests and 13 socket-level
HTTP requests. The complete backend gate executes the existing lifecycle,
permission, privacy, Student/Admin and verification suites, including actual RPC
outage/recovery and immutable version history. Its detailed final results are
recorded in the local integration report. The stale-preview/lease/crash and Google
changed-source/provider cases use controlled test clocks/provider fixtures against
the real disposable PostgreSQL domain model; no live Google acceptance is claimed.

## Deployment boundaries

Institutional profile/namespace/header/value mappings, eligible Student statuses,
catalog entries, explicit source approvals and a trusted issuer still require
operator provisioning. Do not copy synthetic profiles into institutional use.
Google needs an approved server target, a read-only service-account credential
file and live access/changed-source acceptance. The local preview intentionally
reports Google configuration required and never contacts a personal account.

Polygon Amoy needs the reviewed registry deployment, institutional signer/key
provisioning, funded wallet, approved issuer/contract/chain configuration, reliable
RPC, worker operation and real testnet verification. Hosting needs persistent
migration review/backups, production HTTPS/session/CSRF settings, private durable
media, mail delivery, workers, secret management and operational monitoring. Local
Anvil and synthetic acceptance do not certify these external services.
