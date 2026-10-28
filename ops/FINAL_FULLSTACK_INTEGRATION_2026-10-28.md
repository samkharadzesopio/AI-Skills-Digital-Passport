# Frontend, Django and blockchain integration

Baseline: `244996b367d8b91d1f986c4fdeab97860e8556ba`.
Reviewed blockchain: `dc6da57c9f48a3b72fb4fee8e7e54e306c2686b8`
(runtime correction at `71be42d3fea153649de7de494cc720e0955a3314`).
Reviewed frontend presentation: `95861f1f5728dc5fc11ce2e0caec63ae2d5409ea`.

## Branch selection and merges

Lizi's `feature/passport-blockchain-proof` advanced from `e88127d` to `71be42d`,
then to the test/handoff follow-up `dc6da57` during integration validation.
Sopio's named `fix/frontend-blockchain-compatibility` remains at `565d2c1`.
Its relevant navigation/artwork changes were previously adapted into `96ec681`;
that selective integration was not an ancestry merge. Sopio's newer
`feature/frontend-visual-updates` starts at `96ec681` and restores the intended
interface styling and public forms without replacing the application routes.
That is the latest reviewed frontend contribution used here. The obsolete generic
ProductWorkspace from the older branch is not reintroduced over the current
typed Student/Admin interfaces or spreadsheet workflow.

A fresh candidate was created from fetched `origin/integration`. Real merges
retained history, blockchain first (`865877d`), then frontend (`592d52b`). Four
blockchain conflicts concerned only example comments and historical handoffs:
`backend/.env.example`, `blockchain/README.md`, `TEST_REPORT.md` and
`MVP_INTEGRATION_2026-10-27.md`. Resolutions retain the spreadsheet example settings,
both sets of historical evidence, Anvil-first scope, Amoy limitations and the
integration-owned startup runbook. The frontend merge was conflict-free.
The final concurrency fetch found `dc6da57`; its stronger three-confirmation,
independent-RPC and identity-preservation acceptance checks were reviewed and
merged as a follow-up, with no application or contract runtime change.

Original worktrees, branches, stashes, environment files, databases and services
were preserved. No public deployment, public transaction, wallet funding or
production key use is part of this integration.

## Compatibility findings

| Classification | Finding and resolution |
| --- | --- |
| Required security correction | An authorized issuer could replace a Passport with the zero key. Lizi's contract rejects that call before cancellation; the new Solidity test preserves the original state/commitment. ABI/events are unchanged. |
| Deployment compatibility dependency | The pinned runtime changes. The new adapter rejects an older registry as `UNAPPROVED_CONTRACT_CODE`. Actual separate loopback deployments prove old rejection and new acceptance. This is intentional fail-closed behavior, not a pending proof. |
| Required presentation correction | At 768px the new theme removed the content margin while leaving the sidebar visible, covering the Passport. Collapse and menu controls now share the 900px breakpoint. An element-at-point occlusion regression fails before the fix and passes after it; mobile navigation remains operable. |
| Required test portability | The visual check now accepts the existing `BTU_BROWSER_TOOLS`, `BTU_BROWSER_EXECUTABLE` and a run-owned output directory. Existing assertions are retained and the occlusion/menu assertions are added. |
| Non-blocking limitation | Legacy EIP-155 signing remains supported, but no automatic fee bump, same-nonce replacement or stuck-transaction cancellation exists. Retain signed bytes and use the documented reviewed recovery process. |
| Non-blocking diagnostics | Existing bundle-size and jsdom React `act(...)` advisories remain. |
| External dependencies | Institutional source/issuer/grants, live Google/Classroom/SMTP, persistent hosting/storage and public Amoy acceptance are separate from disposable local acceptance. |

No endpoint, DTO, authentication, CSRF, private ownership or migration mismatch
was found in the integrated paths. No Django authentication/permission, credential,
Passport lifecycle, spreadsheet, Student service or public transport implementation
was rewritten. No new schema migration is introduced; integrations `0003`/`0004`
and their tests are preserved byte-for-byte from the baseline.

## Connected application

Live Student routes use the existing authenticated `/api/student/` endpoints for
dashboard, recognized skills, achievements, credentials, current Passport and
version history. The Passport landing keeps the original artwork, permanent versus
version references, exact registered PDF bytes, and backend-authoritative proof
labels. A current badge requires current institutional validity, an authorized
issuer/signer and independently confirmed proof. Local Anvil is labelled local.

Live Administrator pages retain exact-grant Django reads/actions for Students,
credentials, revocation, Passports/PDFs, course mappings, catalog, import history,
strict completion imports and reviewed flexible profiles. Profile previews do not
issue. Confirmation submits the saved digest with explicit approval; pending,
rejected, invalid and duplicate evidence is excluded as before.

Public `/verify` now embeds the existing reference and PDF forms in Sopio's restored
presentation. Separate reference/upload routes and legacy credential/version links
remain. The existing cookie-free public client and native multipart upload remain
unchanged; the registered file is never reconstructed or re-stamped.

Demo Mode remains compile-time/local-development-only. Production builds force it
off, even if the demo flag is supplied. Demo records and actions stay separate
from Live sessions and official issuance. Classroom completion synchronization is
explicitly simulated; catalog/mapping administration remains read-only where no
approved write API exists; the Gap Analyzer remains Coming Soon. Google reports
configuration required without live credentials. No personal Google account is used.

## Acceptance and reproduction

```text
python -B ops/run_isolated_tests.py --full --spreadsheet
cd blockchain
npm ci --ignore-scripts
npm run check
npm test
cd ../frontend
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

Run `check:preview` with `VITE_ENABLE_DEMO=true`. Run
`node scripts/check-visual-restoration.mjs after` with isolated Playwright/Chrome
paths and `BTU_VISUAL_OUTPUT` outside source control. The screenshot/DOM/provider
fixture checks are synthetic tests, not live-service evidence.

Fresh gates passed: 611 Django tests (613 discovered, only the same two legacy
reference-SQL exclusions), 38 focused spreadsheet tests and 13 socket HTTP calls,
12 Solidity tests with exact artifact reproduction, all 11 HTTP/Anvil journeys,
and public/Student/Admin real UI HTTP drivers with 35/63/142 proxied requests.
Final graphical acceptance passed 10 journey groups with 72 actual browser API
responses, including Live tablet occlusion/menu checks and credential revocation.
Frontend build/lint, the existing regression scripts, seven-width variable-content
layout checks and the restored-design five-width check passed. The later
`dc6da57` test-only follow-up is also exercised through a fresh `--chain-http` gate;
the exact final log/merge commit is recorded in the local report.

The local `../final-fullstack-20261028` evidence folder holds exact command logs,
read-only Git snapshots, runtime-transition/deployment checks, real Chrome driver,
screenshots and final acceptance results. Its helpers use fresh owned PostgreSQL,
temporary media/mail/signers and real Anvil, not persistent settings or data.
The graphical journey covers Admin password authentication, row-4 reordered Excel
preview, explicit confirmation, one persisted award/achievement/credential,
durable Passport/PDF workers, actual Anvil confirmation, Student OTP login,
exact-byte download, anonymous reference/PDF verification, tampering, duplicate
replay, missing-grant/CSRF/digest/profile/format denials, both embedded public forms
and revocation. No API responses are intercepted in this journey.

Revocation semantics are intentionally precise: the permanent reference follows
the current snapshot. If the only credential is revoked, the refreshed empty
snapshot is unverifiable; the original version reference and exact original PDF
report `REVOKED`, while registered-byte authenticity/history remain preserved.
The existing complete HTTP/Anvil suite separately tests replacement, historical
versions, invalid proofs, RPC outage/recovery, issuer trust, permissions and privacy.

## Staging assessment and remaining gates

This is a candidate for a **new, configured staging environment** after the local
gates pass. It is not proof that any hosted environment has been deployed, migrated
or accepted. No persistent deployment preflight was run against existing resources.

- Preserve any existing deployment/database and all immutable signed operations,
  PDFs and history. Do not point old rows at a new registry address. The corrected
  artifact does not upgrade an old contract; an existing institutional deployment
  needs a separately reviewed registry/history transition. A fresh staging rehearsal
  can use a fresh database and corrected local registry.
- Provision institutionally approved Student status values, fixed trusted BTU
  issuer, exact administrator grants, source allowlists, profile versions,
  evidence namespaces/catalog mappings and identity approval process.
- Use `DEBUG=false`, independent managed secrets/OTP HMAC keys, HTTPS hosts/origins,
  secure cookies and an explicitly trusted reverse proxy. Route private `/api/`
  traffic through the same origin and retain SPA fallback routing. Normal settings
  require TLS PostgreSQL and encrypted SMTP; test settings are not deployment settings.
- Review migration plans and backups on owned staging PostgreSQL before applying.
  Provide private durable PDF/media storage shared by web and workers. Do not expose
  the media directory as an anonymous file tree. Configure WSGI/static serving,
  durable mail/refresh/publication/blockchain workers, health checks and monitoring.
- Anvil requires a supervised private loopback service, retained chain state and
  its actual corrected registry/issuer configuration. Keep its administrative RPC
  private. Never reuse Anvil keys on public networks.
- Google needs institution-approved targets and read-only service credentials plus
  live changed-source/error acceptance. Real Classroom connectivity remains pending.
- Amoy remains prepared, not publicly validated: obtain explicit deployment
  authorization, institutional custody/admin/issuer policy, funded testnet accounts,
  HTTPS RPC, corrected contract deployment and independently verified public
  receipts/events. Local Anvil configured with chain ID 80002 is only a local
  envelope/adapter rehearsal. It is not Polygon Amoy acceptance.

No fee, confirmation, runtime pin, source approval, permission or privacy assertion
was relaxed to obtain passing results. Existing developer branches and `main`
must remain unchanged during delivery; final commit/ref verification is recorded
in the local report and Git history.
