# Frontend publication handoff

Date: 2026-10-27. Branch: `feature/frontend-passport-ux-stabilized`.

## Preservation and scope

This branch starts at frontend commit `6b5bd0ba69d4d7a1481ad3ffeb2c20e4001067dc` and preserves the 49 reviewed frontend files from the staged, unstaged and untracked state of `fix/frontend-blockchain-compatibility`. A separate publishing worktree leaves that checkout and its index intact. Local environment files, dependencies, build output, browser screenshots, database files and credentials are excluded. No backend, PDF template or blockchain implementation is changed.

The included frontend implements cookie-session student OTP and administrator login, guarded student/admin workspaces, current and historical passport views, version-bound PDF controls, sharing, permission-aware issuance/revocation/import interfaces, public passport/PDF verification, isolated demos, and the official-artwork React passport with responsive lossless pagination. Classroom previews remain simulated. Backend authorization is still required for every private operation.

## Compatibility review

Earlier integration documents describe their historical inspected revisions. The publication fetch observed `origin/integration` at `bec0d8323ff98cb9e4e83c51f607d23d1e9ab46a`, which includes newer blockchain backend work. This branch does not merge that revision. The isolated local backend worktree remains at `cc74833d792f64a9c37764e25cff7108aa524eea`.

A small publication fix allows additional string-valued backend capabilities without invalidating an administrator session. Only recognized capabilities enter the frontend permission model; unknown-only grants do not authorize a workspace, and malformed capability types still fail. Regression cases cover `manage_legal_identity` and `manage_passport_lifecycle` alongside existing grants. No corresponding new action UI is implemented.

Remaining integration requirements:

- Run actual Django/PostgreSQL authentication, sessions, CSRF, authorization, imports, issuance, revocation, public verification and PDF generation/download journeys. No real service end-to-end success is established by these frontend checks.
- Agree and implement the final proof-success contract and current-passport eligibility for modern `BLOCKCHAIN_VERIFIED` records. The adapter deliberately never reports blockchain success, even for provisional `CONFIRMED` evidence; modern proof-dependent passports are not yet activated as current-valid shared passports.
- Reconcile newer public `NOT_ISSUED` responses, currently rejected as unsupported rather than presented as successful verification.
- Confirm lifecycle, historical-PDF, issuer, chain/environment, reference binding and freshness policies against the final backend. Do not infer blockchain confirmation from a status string.
- Full approved Gilroy webfonts remain a visual fidelity dependency; approved logo/title vectors and original stamp assets are included.

## Validation

Production build (including TypeScript), repository `lint` (Oxlint, not ESLint), and all eleven existing non-browser checks passed on the publishing copy. Coverage includes authentication, architecture, administrator guards, verification, Demo Mode, routes, PDF/template integrity, product flows, public HTTP transport fixtures, lifecycle compatibility and the React passport card. The additional browser layout check uses isolated Chromium and synthetic data at 1920x1080, 1366x768, 1024x768, 768x1024, 390x844 and 375x667; its final outcome is recorded in the publication report.

These tests use mocks, disposable HTTP fixtures or API-blocked browser contexts, not real Django, PostgreSQL or chain transactions. The production build retains the approximately 763 kB JavaScript chunk warning. No physical-device Safari/Firefox test is claimed.

Reproduce from `frontend`: `npm ci`, `npm run build`, `npm run lint`, then all `check:*` scripts. For the demo route checks set `VITE_ENABLE_DEMO=true` in the command environment only; tests that exercise Live Mode override it and production builds disable it. The optional layout check requires a separately installed Playwright/Chromium tooling directory specified by `BTU_BROWSER_TOOLS`; see `dashboard-passport-ux.md`. Do not copy local secret-bearing environment files into the branch.
