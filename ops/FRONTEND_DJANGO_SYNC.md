# Sopio frontend / Django integration candidate

## Source and delivery boundaries

- Starting integration: `6ddd218c1bd1cc94853f59feafa723fb23aae72e`.
- Sopio's pushed branch: `feature/frontend-visual-updates`, commit
  `2199a3727a2675097121c7a45326a7f83cac9e98`.
- Candidate: `integration-candidate/sopio-django-20261028`, in an isolated worktree.
- Do not push or merge shared integration without the owner's explicit approval.
  Main and existing worktrees/stashes are preserved. No deployment is performed.
- The Google backend feature `22aeaa4129b536fa001d2d392564244200bac978` is not
  merged. No Lizi branch, blockchain file, Anvil/Amoy configuration or proof
  implementation is changed. No real Google API or credential is used.

## Merge resolution and interface

The only content conflict was `frontend/src/admin/live/integrations.tsx`.
Sopio's grouped navigation, compact dashboard, source picker, local Excel preview,
result wording and responsive design are retained. Integration's existing
`SpreadsheetImports` component is also retained at the top of Data Imports.
The obsolete statement that Django has no validation-preview endpoint is removed.

The reviewed form handles BTU awarded-skill workbooks using an operator-approved
profile; the completion adapters below retain the existing course-completion
schema. Local workbook display is explicitly different from Django validation.
No local schema preview can approve students, skills, evidence or duplicates.

Existing routes remain:

| Operation | Django API |
|---|---|
| List enabled approved profiles | `GET /api/integrations/import/profiles/` |
| Validate awarded-skill Excel | `POST /api/integrations/import/excel/preview/`, multipart `profile_id` and `file` |
| Validate configured Google source | `POST /api/integrations/import/google-sheets/preview/`, JSON `profile_id` only |
| Read the owner's private preview | `GET /api/integrations/import/previews/{id}/` |
| Confirm exact reviewed snapshot | `POST /api/integrations/import/previews/{id}/confirm/`, JSON `confirm: true` and `snapshot_sha256` |
| Existing strict completion adapters/history | Existing `service.ts` endpoints, unchanged |

No API response shape, authentication, CSRF or permission code is changed.
Missing CSRF and a wrong digest are rejected. Replay retains the original
result and creates no duplicate achievement or credential. Persisted import
history and event inspection remain available after confirmation.

## Official workbook and approval boundary

The existing `backend/data/students.xlsx` was inspected read-only for metadata
and its recognized header row only. It contains `Passport Skill Records`, header
row 4, 20 columns and 998 rows. No student data was imported or displayed from
this original file, and its bytes remain unchanged.

Those headers describe awarded skills, not the seven-column completion schema.
They include Student ID, Record ID, Skill ID and Date Earned, plus identity,
catalog and synchronization fields. They do **not** contain an independent
institutional approval decision. Passport Sync Status and the other output
fields cannot authorize issuance or serve as proof of synchronization.

The real Chrome fixture creates two separate fictional workbooks:

1. The original 20-header shape, row 4 and worksheet name, with synthetic values.
   It intentionally puts `CONFIRMED` in Passport Sync Status. Django detects
   the awarded-skill mapping but returns institutional review required, zero
   eligible records, and disables confirmation. The sync output is not trusted.
2. A synthetic copy with a separate `Institutional Approval` column and an
   explicitly enabled test profile. It yields one valid, one duplicate, three
   invalid and two review rows; only the independently CONFIRMED award issues.

An institution must supply approved evidence/profile decisions before the
original format can issue. This integration does not invent those decisions,
weaken approval rules, modify the original workbook, or add backend policy.
Successful persistence is displayed through Django row results, receipts,
credentials and import history; the source workbook is not written back.

## Validation and mode separation

Frontend checks include the TypeScript production build, lint and existing
architecture/admin/auth/Student/verification/Demo/preview/Passport/spreadsheet
regressions. `check:preview` requires Demo Mode; scope `VITE_ENABLE_DEMO=true`
to that command only. Production build and the real HTTP journey use false.

The two new Sopio browser checks accept `BTU_BROWSER_TOOLS`,
`BTU_BROWSER_EXECUTABLE` and task-owned cache/artifact paths, retaining their
original defaults. This avoids a machine-specific missing temporary Playwright
installation without adding application dependencies. The old real Admin HTTP
driver now selects Sopio's new dashboard labels, result heading and Google
source tab; its existing backend/security assertions are retained.

With the existing isolated Playwright installation and Chrome available:

```powershell
$env:BTU_BROWSER_TOOLS = 'C:\path\to\isolated-browser-tools'
$env:BTU_BROWSER_EXECUTABLE = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$env:BTU_TEST_ARTIFACTS = 'C:\path\to\new-local-review-artifacts'
python -B ops/run_isolated_tests.py --frontend-django
```

This adds a focused compatibility mode to the existing owned-resource runner:
system/schema checks; relevant account, API and spreadsheet tests; existing
Excel/Student/Admin/public HTTP acceptance; and native Chrome acceptance.
`--frontend-browser` runs only the new Chrome journey after safety/schema checks.
Both allocate a new loopback PostgreSQL cluster and never load `.env`, adopt a
database, start Anvil or contact an external Google service.

The native Chrome test uses actual React, the Vite proxy, Django sessions/CSRF,
synthetic PostgreSQL records, local-memory OTP delivery and the actual PDF
service. No API responses are intercepted. It checks Admin navigation, the two
awarded-skill preview cases, confirmation, persisted history/replay, Google's
safe missing-credential response, Student OTP/Passport/skills/PDF download,
responsive layouts, and anonymous reference/original/modified-PDF results.

It inherits existing API test settings without changing blockchain settings or
proof behavior. Proofs are asserted `NOT_CONFIGURED` and not verified; sharing
stays disabled. Public reference results are compared to the actual backend
response. This is backend record/PDF acceptance, not blockchain authenticity,
SMTP delivery, institutional production approval or deployment readiness.
The older chain-dependent `check:browser` variant is outside this task; no
chain success is fabricated to make it pass.

## Remaining backend responsibilities

- General security-audit browsing has no dedicated sanitized read API/grant in
  the current contract. Existing credential/import/sync history remains usable.
- Live catalog/mapping Add/Edit and generalized activity mappings require
  separately approved backend write/policy APIs; current mappings are courses.
- The Google reviewed UI already works with integration's existing API. The
  unmerged Google feature adds optional server range/credential/preflight tools,
  not a frontend API prerequisite. Real Google authentication/sharing/read and
  acceptance remain deferred to explicit later approval.
- Classroom remains the existing labeled simulation. No real connector or
  unrelated backend functionality is introduced.
