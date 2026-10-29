# Admin frontend integration review

Base: origin/integration at 6ddd218c1bd1cc94853f59feafa723fb23aae72e.
Source: 2199a3727a2675097121c7a45326a7f83cac9e98.
Branch: review/admin-integration-2199a37.

Incorporates grouped capability-aware navigation, dashboard workflow actions and truthful metrics, student search labels, catalog and course-based activity search, credential evidence details, completion-source selection, local workbook previews, responsive admin styling and the source regression tests.

## Conflict resolution

The single conflict was frontend/src/admin/live/integrations.tsx. Retained integration's SpreadsheetImports component (approved profiles, immutable server snapshot, exact-digest confirmation, expiry and explicit retry controls) alongside the source commit's completion-evidence Excel/Sheets controls, local first-ten-row preview, outcomes and persisted event history. Updated the source's obsolete no-server-preview wording to distinguish the two workflows. Added an early file-selection generation check to prevent a stale asynchronous workbook result from overwriting a newer selection. The live admin DOM regression explicitly asserts that approved-profile controls remain mounted and disabled without a selected profile.

Backend, blockchain, authentication, student components, routing, API adapters and reviewed spreadsheet contracts/services are unchanged from the integration base.

## Validation

Passed: build (tsc -b plus Vite), lint, check:architecture, check:admin, check:preview, check:verification, check:demo, check:passport, check:auth, check:student, check:passport-card, check:integration, check:spreadsheet and check:passport-layout.

Browser tests passed: check-admin-ux.mjs (32 combinations over eight pages and four viewports; no page errors or Demo API calls), check-admin-import-preview.mjs (actual synthetic XLSX decode, local row preview, invalid-file cleanup and zero mutation requests). Desktop dashboard and mobile imports screenshots were visually inspected. Passport graphical checks passed all seven sizes from 375x667 through 1920x1080, including all 33 variable-content pages without clipping or internal scrolling.

Build retains the existing bundle-size warning (main JS approximately 534 kB). Parallel DOM harnesses reported an auxiliary HMR-port collision; assertions passed and isolated graphical tests passed. Real Django/PostgreSQL/Google/Anvil end-to-end acceptance was not run; fixture tests do not establish real issuance, OTP, Google access or blockchain confirmation.

## Preview and handoff

Demo configuration is local and ignored: frontend/.env.local contains VITE_ENABLE_DEMO=true. Vite runs localhost:5175 with strict port selection. Ports 5173 and 5174 are preserved. Generated screenshots are local review artifacts and excluded from the commit. The official integration branch and remote are unchanged.

Ready for merge review after visual approval, with the stated real-service validation limitation.
