# Administrator workflow simplification — 2026-10-28

Branch: `feature/frontend-visual-updates`; starting commit `95861f1`. Changes are local and uncommitted. Existing `frontend/restoration-review/` artifacts were preserved. No backend, migration, blockchain, authentication, API client, contract parser, or student-facing component was modified. No merge or push occurred.

## Reviewed architecture

`App.tsx` selects the existing fixture-backed administrator workspace in Demo Mode and `admin/live` pages in Live Mode. Live routes retain the outer administrator boundary and per-page capability gates. APIs independently authorize each read/write; navigation filtering is not authorization. Inspected contracts are documented in `ops/ADMIN_INTEGRATION.md` and implemented in `admin/live/service.ts` and `contracts.ts`.

Live capabilities cover statistics, student search/detail and permitted record edits, achievement-based credential issuance/revocation, persisted catalog/course mappings, imports and events, simulated Classroom sync/retries, credential history, Passport versions/PDFs, and public verification. Demo catalog/mapping drafts remain in memory, and official mutations stay disabled.

## Changes

- Shared navigation groups both admin modes into Overview, Learning Data, Operations, Trust & System, and Secondary Features. Existing URLs remain unchanged. Verification links to the public function; Passport Records remains accessible for registered snapshots, proof and transaction information, exact-version PDF controls, and verification links. Simulated Classroom is secondary and explicitly labeled. Duplicate verification links and oversized sidebar promotion were removed. Official BTU logos replace the text-only wordmark.
- Dashboard emphasizes Import Activity Records, Review Credentials, and View Students, with a compact workflow guide. Live student and credential totals come from the existing statistics API. Review-queue/global import-error metrics explicitly say unavailable because the contract does not supply them. Recent Activity uses the first returned persisted import runs only when `import_completions` is granted; it does not claim a complete audit feed or an aggregate error total. Demo totals/activity come exclusively from labeled fixtures. Decorative issuance charts were removed.
- Student table keeps server search/filter/pagination, privacy boundaries, detail links, existing permitted create/edit controls, verified achievements, issuance, and Passport access. Search now explicitly says name/email/student ID. No Passport is embedded in the student table.
- Live Skills Catalog adds search across the current page's skill/code/category/description, with an explicit pagination limitation and empty state. Demo catalog description search was expanded without removing existing category/skill edit controls or recursive relationships.
- The interface calls the separate mapping page Activity-to-Skill Mapping. Live mappings add search and an empty state. Both modes explicitly explain that the current backend supports courses only; no workshop/seminar/event write capability is implied. URLs, `course_id`, approved skill codes and policy semantics are unchanged.
- Live Data Imports adds source selection between the existing Excel and configured Google Sheets adapters. Excel displays the first ten workbook rows locally, preserves schema/file-size/row/header checks, and requires the existing confirmation before submission. Local preview makes no server writes and is not server approval. Django still validates students, approved course mappings, duplicates and evidence at submission; valid rows may persist alongside failures. Persisted results, sanitized row errors, run/event history, replay controls and partial-outcome warnings remain. Demo preview now clearly explains its illustrative legacy schema and lack of official mutations.
- Credential lists add supporting earned skills, source activity references, issuance state and a truthful explanation that proof belongs to the associated Passport. Existing credential details preserve public verification, revocation state, exact supporting evidence and lifecycle history. No proof/transaction field was invented or inferred from issuance.
- Admin-only CSS provides consistent compact cards/tables, grouped navigation, action hierarchy, responsive forms, bounded table scrolling and a tablet sidebar offset. Student Passport artwork/layout is unaffected.

## Preserved functionality and limits

All existing student management controls remain behind their original grants; only the interface was reorganized. Credential issuance still uses persisted VERIFIED achievements and stable retry keys; revocation still requires a reason and confirmation. Import, retry, sync, generation/download and public verification adapters are unchanged. Anvil/Amoy proof parsing, reference binding, confirmation requirements, lifecycle distinctions and public privacy projections are unchanged.

Backend dependencies intentionally remain visible:

1. No dashboard review-queue or global import-error aggregate endpoint exists in this contract.
2. General security audit reading needs a dedicated sanitized API and grant. Credential/import/sync history remains available through existing authorized projections.
3. Live catalog/mapping Add/Edit needs an approved write/approval workflow. Existing Demo Mode draft editing remains available.
4. Multi-type activity mapping requires a backend extension; existing mappings are course-based.
5. There is no separate authoritative spreadsheet preview/validate-only endpoint. Local preview cannot certify unknown students, duplicates or approved activities. Configured Google Sheets requires operator-supplied approved source/credentials; arbitrary URLs are not accepted in Live Mode.
6. Classroom remains backend-simulated. Its current controls are retained and labeled; no real connector was invented.
7. Credential list records do not contain a complete blockchain proof or student display name. Existing student/Passport links provide the authorized detail journey; no extra private fields or proof verdicts were fabricated.

## Validation

Passed `npm.cmd run build` (includes TypeScript), `lint`, `check:architecture`, `check:admin` (fixture/domain and live DOM contracts), `check:preview`, `check:verification`, `check:demo`, `check:passport`, `check:auth`, `check:student`, `check:passport-card`, and `check:integration`.

Updated admin regression assertions cover unavailable dashboard metrics, grouped navigation, catalog search/no matches, course-only activity policy, and source selection. Existing permission combinations, denied reads/actions, malformed responses, network errors, empty states, server pagination, CSRF rebootstrap, cooldowns, issuance retry idempotency, revocation, configured-Sheet failure and expired-session checks still pass. The preview regression now asserts workflow actions and absence of the removed chart instead of expecting decorative analytics.

`node scripts/check-admin-ux.mjs` passed 32 rendered Demo Mode page/viewport combinations across dashboard, students, catalog, mappings, imports, credentials, audit and Classroom at 1366×768, 1440×900, 768×1024 and 390×844. It checks mobile navigation, document overflow, grouped navigation, required dashboard actions, demo disclosure, zero API requests and zero browser errors. Screenshots/results are local under `restoration-review/admin/` relative to the command's working directory. Desktop dashboard and mobile mappings screenshots were visually inspected. Tables use horizontal scrolling inside their container on narrow screens.

`node scripts/check-admin-import-preview.mjs` passed using a real synthetic XLSX archive and intercepted anonymous-free test administrator/empty-history responses. It exercises actual workbook decoding, displayed row values, enabled review action, invalid-file cleanup, disabled invalid submission, and zero mutation requests during preview. No real account or academic record is touched.

Initial checks caught an incomplete automated dashboard edit and an obsolete dashboard assertion; the file was reconstructed from its unchanged starting revision with the intended edit and revalidated. Browser-test selectors and breakpoint assumptions were corrected; the tablet check exposed a real shared-shell overlap, fixed only within admin CSS. The XLSX fixture resolved its existing ZIP dependency through the package's exported Node entry. No test was removed or security expectation weakened.

Build's main JavaScript chunk dropped from about 789 kB to 521 kB after removing the demo chart imports; Vite still reports the existing >500 kB warning. No new application dependency was added. Browser scripts use the existing isolated Playwright installation; the workbook test uses read-excel-file's existing ZIP dependency.

Real Django/PostgreSQL/Anvil acceptance was not performed: local Django configuration and service prerequisites remain unavailable from the earlier diagnosis. Fixture tests do not establish real imports, issuance, stored PDF generation, OTP delivery or blockchain confirmation. The existing real-service browser driver still requires a separately prepared owned environment.

## File handoff

Modified: `src/layouts/AdminLayout.tsx`; `src/admin/live/{Layout.tsx,pages.tsx,integrations.tsx}`; `src/admin/{pages.tsx,i18n.ts,CatalogPage.tsx,MappingsPage.tsx,ImportsPage.tsx}`; `scripts/check-admin-live.mjs`; `scripts/check-preview.mjs`.

New: `src/admin/Navigation.tsx`, `src/admin/ux.css`, `scripts/check-admin-ux.mjs`, `scripts/check-admin-import-preview.mjs`, and this report. Generated screenshot directories are local review artifacts. All changes are uncommitted; original worktrees and previously published branches are preserved. Integration/production readiness is not claimed.
