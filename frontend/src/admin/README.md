# Admin frontend integration

All current admin records are fictional fixtures. `mock.ts` is independent of student services. `store.tsx` keeps catalog and mapping drafts in the `['admin', 'demo']` query cache for this tab; refreshing or resetting discards them. No production mutation adapter is connected. `services.ts` rejects every official action without issuing a network request or changing a record.

## Local preview

Set `VITE_ENABLE_DEMO=true` in `frontend/.env.local`, restart `npm.cmd run dev`, and open `/admin/dashboard`. The shared development-only flag opens both Student and Admin mock workspaces with a Demo Mode banner. It does not authenticate or query a real session, grant permissions, access private APIs, or enable official actions. Vite build/preview always disables it. The old separate preview flags are no longer used.

## Routes

- `/admin/dashboard`: totals derived from demo records, sample issuance chart, recent demo activity.
- `/admin/students`, `/admin/students/:id`: search, program/status filters, sortable paginated list, associated skills, credentials and passport status.
- `/admin/skills`: searchable recursive catalog, create/edit forms, stable IDs and parent relationships. Edits cannot move nodes. New/edited skills remain drafts; editing a skill clears affected mapping approvals.
- `/admin/course-mappings`: approved-course selection, multiple approved skills, mapping draft state and approval metadata. Local edits never approve a mapping.
- `/admin/credentials`, `/admin/credentials/:id`: search/status filters, details/evidence, issuance request form, reason-validated revocation request. Actions always report unavailable; no issuance or revocation is simulated.
- `/admin/classroom-sync`: fictional failed/pending event history, attempts and failure information, sample payload preview, retry request. Preview and retry do not run a synchronization.
- `/admin/imports`: local `.xlsx` parsing/validation, row preview/errors, Google Sheets URL input, unavailable server-preview/import requests, fictional import history. There is no successful-import state without a backend result.
- `/admin/audit-logs`: searchable, sortable, paginated, read-only fictional audit history.

Tables use a shared search/sort/pagination component. Native modal dialogs support keyboard focus containment, Escape and labeled controls. UI copy uses English/Georgian dictionaries; fixture record names and technical identifiers remain source data. Dates render in Asia/Tbilisi. Admin styles are scoped to preserve student and verification layouts.

## Import proposal

Local preview currently accepts nonempty `.xlsx` files up to 5 MB and at most 1,000 data rows on the first worksheet. Required columns are exactly `student_id`, `course_id`, `skill_id` in any order. These are proposed frontend preview columns, not a confirmed university import contract. Rows check required values, duplicate triples, student IDs, approved courses, approved skills and approved course mappings against the demo directory. Preview results do not change any records or prove server-side eligibility.

Google Sheets links are validated locally but never fetched by the browser. Private-sheet authorization and parsing require a server connector. Legacy `.xls`, additional worksheets, arbitrary field mapping, server validation, import jobs and reconciliation are not implemented. Production must revalidate uploaded contents and every referenced ID, regardless of local checks.

## Required backend contracts

The following route shapes are **proposals only**, not confirmed endpoints and not used by the current adapters:

- Session/permissions endpoint: authenticated identity, explicit administrator capabilities and session-expiry behavior. Every admin endpoint must enforce Django permissions.
- `GET /api/admin/overview/`: authorized totals, issuance time series, reporting timezone and period.
- `GET /api/admin/students/`, `GET /api/admin/students/{id}/`: server search/filter/order/pagination and authorized skill/credential/passport summaries.
- Category/subcategory/skill list, create and patch endpoints: stable IDs, nested parent relationships, validation errors, taxonomy version and concurrent-edit protection. Confirm whether moving records is allowed.
- Course catalog and course-skill mapping read/update endpoints: approved courses/skills, multiple IDs, draft/approved status, approver/time, separate approval permissions and version checks.
- Credential list/detail, issuance and revocation endpoints: authoritative issuer/evidence, issuance prerequisites, validated revocation reason, permission checks, idempotency and asynchronous-result states.
- Sync-event list/detail, dry-run preview and retry endpoints: authoritative event status, failure details, attempt count and confirmed retry/job outcome. Never interpret an accepted request as completed sync.
- Import preview endpoints for multipart Excel uploads and authorized Google Sheets sources: structured row/field errors and an expiring validation token. Commit must accept the validated token, use authorized references and return a job ID; job polling/history supplies actual completion/failure results.
- Read-only audit-log endpoint: actor, action, UTC timestamp, affected record, stable event ID, server pagination/filtering, redaction rules and immutable history.

Confirm response shapes, validation errors, CSRF/session cookie handling, account-scoped cache keys, HTTP 401/403 behavior, conflict responses, retry/idempotency policy and data minimization before replacing fixture services. Clear admin query caches on logout/account changes. Never expose production admin data through development preview mode.

## Validation

`npm.cmd run check:admin` checks domain invariants and unavailable official actions. `npm.cmd run check:architecture` checks route rendering, access boundaries and independence of public/student/admin data. Build and lint remain required. These checks do not replace browser/mobile interaction, dialog keyboard, real workbook file-selection, or backend integration testing.
