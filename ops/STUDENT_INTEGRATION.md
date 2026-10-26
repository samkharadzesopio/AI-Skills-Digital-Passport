# Real Student frontend integration — 26 October 2026

The authenticated Student milestone is complete and tested with persisted PostgreSQL records through the real Vite proxy and Django APIs. The React driver is jsdom with real HTTP, rather than a graphical browser. This is local synthetic acceptance, not a production deployment or a live university connection.

## Integrated files and behavior

The existing `work/2026-10-26-real-authentication` frontend already includes preview `e8f2f83`. It was integrated into the existing `integration` branch without replacing newer backend files. No branch, worktree or clone was created.

- `frontend/src/student/contracts.ts`: runtime parsing of actual Django DTOs, paginated responses and PDF metadata; failed/malformed responses never substitute demo records.
- `student/service.ts`: same-origin private APIs, page selectors, UUID validation, safe errors and real binary downloads. Pagination never follows a server-supplied URL; no Student ID is accepted as a scope selector.
- `student/adapter.ts`: issued snapshot view grouped by category and one subcategory. No invented recursive classification, evidence relationship, assessed proficiency, signature or verification verdict.
- `student/queries.ts`: cancellable account-scoped queries with no persistent private cache.
- `student/pages.tsx`, `student/PdfActions.tsx`, `student/student.css`: records/details/history, loading/error/empty/retry states, current and historical PDF actions using existing cards/layout styles.
- `App.tsx`, `auth/SessionPanel.tsx`: live nested routes/navigation replace the placeholder; existing account guards, session restoration and logout remain in force.
- `components/PassportPreview.tsx`: adds `IssuedPassportPreview` over actual snapshots, preserving the separate proposed-schema demo renderer.
- `vite.config.ts`: preserves the same-origin proxy and default backend. Optional server-side `BTU_DEV_API_TARGET` supports isolated local acceptance ports.
- `scripts/check-student.mjs`, `scripts/check-student-http.mjs`, `ops/test_student_e2e.py`: adapter/DOM tests and real React-to-Django HTTP acceptance. Prior auth/architecture tests now expect a live dashboard rather than a placeholder.

**Backend changes: none.** No backend application, migration, authentication/permission service, original BTU PDF template, Georgian renderer, or public verification implementation changed. No dependency was added. Admin's existing demo interface/access boundary remains intact.

## Connected pages and APIs

All private endpoints use the existing Axios client: same-origin cookies, no-store, redirect rejection and CSRF bootstrap on writes.

| Student page | Actual endpoint |
|---|---|
| Login/logout/session | `/api/accounts/csrf/`, `otp/request/`, `otp/verify/`, `me/`, `logout/` |
| Dashboard and read-only profile | GET `/api/student/dashboard/` |
| Skills | GET `/api/student/skills/?page=N` |
| Achievements | GET `/api/student/achievements/?page=N` |
| Credentials and detail | GET `/api/student/credentials/?page=N` and `/api/student/credentials/{uuid}/` |
| Current Passport | GET `/api/student/passport/` |
| Version history/detail | GET `/api/student/passport/versions/?page=N` and `/api/student/passport/versions/{uuid}/` |
| Current PDF | POST `/api/student/passport/pdf/` with `{}`; GET `pdf/status/` and `pdf/download/` |
| Historical PDF | Same operations under `/api/student/passport/versions/{uuid}/pdf/` |

Routes are `/student/dashboard`, `/profile`, `/skills`, `/achievements`, `/credentials`, `/credentials/:id`, `/passport`, `/passport/versions`, `/passport/versions/:id` within the Student namespace.

Dashboard counts, category distributions, recent achievements and credential states come from Django. Invented progress percentages/hours/trends remain only in labelled Demo Mode. Earned achievements are distinguished from current credential validity. The existing serializer's `competency_level` is displayed as learning format, not assessed proficiency.

The live Passport preview shows actual snapshot issuance, category/subcategory, credential references, public Passport/version references and latest-versus-historical currency. Issuance is not labelled currently verified. The serializer provides no historical holder/profile or skill-to-credential/evidence edges, so the adapter does not reconstruct them from current data or guess associations.

PDF actions inspect existing status first, reuse available documents, poll PENDING/GENERATING without repeating POSTs, and allow explicit retries. HTTP 409, template overflow 422, 429 Retry-After and 503 have safe messages. Downloads require real PDF bytes/content type and the backend's fixed safe filename pattern. Requests abort on unmount, private Blob URLs are revoked, and PDFs are not cached in query state. The browser handles file saving; acceptance validates the actual downloaded Blob/filename.

## Tests executed on the implementation

| Check | Actual result |
|---|---|
| Combined Django regression: api, integrations, skills, credentials, passports, students, accounts, verification | **463 passed in 166.481 s**; 465 discovered, two pre-existing reference-SQL comparisons explicitly excluded by the existing runner |
| Django system check; migration drift; whitespace | PASS; no issues, no changes detected |
| TypeScript/production build; lint | PASS; existing large-bundle warning remains |
| check:architecture, check:auth | PASS: role/access/session/failed-logout/storage protections retained |
| check:student | PASS: DTO adapters, flat classification, malformed contracts, pagination origin isolation, states, loading/error/empty/retry, historical PDF/CSRF, overflow, in-progress polling without duplicate POSTs and URL cleanup |
| check:admin, check:verification, check:demo, check:passport | PASS |
| check:preview | PASS with its required local demo flag; original environment restored afterward |
| `ops/test_student_e2e.py` | PASS; **63 real proxied requests** in final run, no mocked HTTP/API responses |

Real HTTP acceptance mounts actual React routes, signs in through the OTP form, displays database-backed dashboard/profile/skills/achievements/credentials with VALID/EXPIRED/REVOKED states, opens credential details, current Passport and version history, generates/downloads current and historical PDFs, and verifies downloaded bytes through the real public registry. It restores a fresh client after refresh, logs out, checks session/private-cache removal, and signs in as a second student. Foreign credential/version/download requests return 404; missing-CSRF writes return 403. PostgreSQL confirms exactly one issued document per requested version after repeated downloads.

The harness uses safe loopback-only PostgreSQL settings, production URL routing and disposable `test_student_frontend_e2e`. Synthetic mail is shared with the local driver through a temporary directory, never an application HTTP endpoint. All fixture data/mail is discarded. The driver initially rejected Django's expired logout cookie; corrected test cookie handling passes without changing application logout. Nonfatal React `act` scheduling warnings appear during real asynchronous DOM testing; graphical rendering, keyboard/mobile behavior and the OS save dialog are not certified.

## Reproduce and run locally

Install locked frontend dependencies with `npm.cmd ci` in `frontend`. From repository root, use the existing Python environment and a disposable local PostgreSQL server:

```powershell
$env:FOUNDATION_TEST_PG_HOST='127.0.0.1'
$env:FOUNDATION_TEST_PG_PORT='55435'
$env:FOUNDATION_TEST_PG_PASSWORD='local-test-unused'
$env:AUTH_TEST_PG_PORT='55435'
python ops/test_student_e2e.py
```

The existing auth test harness has an explicit local postgres connection and must be able to create/drop test databases. The script selects an ephemeral backend port and starts/stops Vite itself. It never loads production `.env` or migrates shared/Neon data. Run `npm.cmd run check:student` separately for fast unit/DOM checks; other checks are in package.json.

For interactive development, set `VITE_ENABLE_DEMO=false`, run Django with approved local settings, then start Vite. Default backend remains `127.0.0.1:8000`; the process environment `BTU_DEV_API_TARGET` can select a different trusted local backend. Production still requires same-origin HTTPS routing; Vite's proxy is not included in static hosting.

## Remaining scope and limitations

Historical milestone note: the subsequent [public verification integration](THIRD_PARTY_VERIFICATION.md) supersedes the public-UI parser/configuration limitations described below. Student implementation and its original test evidence remain unchanged.

Demo Mode remains labelled and development-only. Admin management still needs its future capability/API integration. Public verification UI retains its existing opt-in configuration and known Passport/document parser gaps; backend compatibility and downloaded bytes were verified directly. Credential details show the reference and link to the public form without claiming a UI verification occurred.

Career Gap Analyzer and game remain placeholders. Recommendations, blockchain, Neon, live Classroom access, full Admin integration and redesign were not developed. Blockchain remains mandatory outstanding work. No live SMTP/institutional access, staging deployment, production load, graphical-browser/accessibility or complete Georgian translation is claimed; new live record labels are English. This report supersedes the historical audit's Student-placeholder/PDF integration findings only.
