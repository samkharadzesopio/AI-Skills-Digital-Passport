# Agent ownership and evidence rules

All specialists use detached worktrees under `C:/Users/User/sth/AI-Passport/fullstack-agent-worktrees-20261028/`. They must not commit, push, change other worktrees, or spawn more agents. Coordinator reviews and applies proposed patches to `feature/fullstack-agent-fixes`. Shared Git metadata is not an isolation boundary.

| Specialist | Owned source paths | Evidence directory / responsibilities |
| --- | --- | --- |
| Frontend | `frontend/src` except `auth/`, session/API authentication services, import files and shared contracts/settings | `frontend/`: all React routes and non-import controls; route redirects, navigation, accessibility, responsive states; preserve visual identity |
| Backend | `backend/apps/api` and existing business services except accounts, integrations, passport/PDF/blockchain services | `backend/`: endpoint/permission/database mapping, security and persistence regressions; no policy invention |
| Imports | `backend/apps/integrations` excluding auth; `frontend/src/admin/ImportsPage.tsx`, `importValidation.ts`, `live/SpreadsheetImports.tsx`, `live/spreadsheet-*`, `live/integrations.tsx` | `imports/`: distinct source formats, statuses, preview/confirmation/sync/replay, simulation and privacy; no real providers |
| Passport/PDF/blockchain | integration-owned passport/PDF services; propose shared edits through coordinator; no contracts/protocol changes | `passport/`: immutable identity/history, visual PDF inspection, local Anvil proof semantics and failure/recovery |
| Independent QA | new audit test scripts only; no app repairs | `qa/`: independently validate other agents' findings and final integrated candidate in real Chrome against actual Django/PostgreSQL |

Coordinator owns `docs/qa/`, router/shared components/contracts/settings, master inventory and final tests. Request ownership before shared-file edits. Source modifications wait until a defect is reproduced and intent established. Unclear product behavior is recorded and referred to the owner before implementation.

Each control receives a stable ID and separate record for distinct actions. Required fields: route, label, source file, role/mode, intended function and source evidence, expected/actual outcome, endpoint, permission, expected database mutation, error behavior, classification, root cause, assigned agent, fix status, regression and browser retest evidence. Pending tests must remain pending; rendering/clickability is not PASS.

Every test uses synthetic records and run-owned disposable PostgreSQL, ports, processes, caches, mail/media and artifacts. Local Anvil only. No production environment loading, real email, credentials, Google/Classroom API, persistent database, public chain, deployment, authentication implementation or smart contract changes.
