# BTU AI Skills Digital Passport frontend

## Run and check

Use `npm.cmd` in PowerShell if execution policy blocks `npm.ps1`.

- `npm.cmd install`
- `npm.cmd run dev`
- `npm.cmd run build`
- `npm.cmd run lint`
- `npm.cmd run check:architecture`
- `npm.cmd run check:admin`
- `npm.cmd run check:verification`
- `npm.cmd run check:demo`
- `npm.cmd run check:preview` (requires the local Demo Mode flag; exercises actual React DOM rendering)

## Routes and access

- `/student/dashboard`, `/student/skills`, `/student/credentials`, `/student/passport`, `/student/gap-analyzer`, `/student/profile`, `/student/game` use `StudentLayout`.
- `/admin/dashboard` uses `AdminLayout`. The functional demo workspace includes overview, students, skills, course mappings, credentials, sync, imports and audit routes. See `src/admin/README.md` for routes and proposed backend contracts.
- `/verify/*` uses `VerificationLayout` and requires no session or student query. Landing, reference, PDF upload, QR review and in-memory results are implemented; see `src/verification/README.md` for inspected backend contracts and integration limits. Unknown paths inside each namespace show a not-found page.
- `/` and the former root-level student page URLs redirect with replacement to `/student/...`, preserving search and fragment. Redirect targets pass through the access boundary before student queries mount.

`src/services/session.ts` deliberately returns `unavailable` until Django authentication and explicit role/permission contracts are confirmed. Student and admin routes deny access by default; there is no fabricated logged-in user. Frontend access boundaries are UX only. Every protected API request and PDF download must still be authenticated and authorized by Django. Never trust browser roles or passport provenance as a security boundary.

For local Demo Mode, create `frontend/.env.local` (beside `package.json`) with `VITE_ENABLE_DEMO=true`, then run `npm.cmd run dev` and restart any existing dev server. Open `/student/dashboard`, `/admin/dashboard`, or `/verify` on the URL Vite prints. `/student` and `/admin` redirect to their dashboard URLs. The single flag replaces the old separate preview flags, which are no longer read.

A visible Demo Mode banner links all three workspaces. Mock student/admin data is reused; no session query, Django login or private API request is performed. Official issuance, revocation, imports, sync and public verification results/requests are blocked; local catalog drafts, local spreadsheet validation and all existing placeholder pages remain available. The nested passport data/template requirements are unchanged. Demo users are never authenticated identities.

Demo Mode requires Vite's local serve command, DEV=true, PROD=false and the exact string flag true. Build and preview commands force it off, including builds with NODE_ENV=development. To turn it off, remove the flag or set it false and restart Vite. `npm.cmd run build` and `npm.cmd run preview` intentionally retain real access boundaries; opening `dist/index.html` directly is not a demo preview workflow.

## Passport representation

`src/contracts/passport.ts` and `src/contracts/passport.schema.json` define a **proposed v2** language-independent JSON representation. They require approval against the actual BTU template and Django serializer; they are not an assertion that the backend already supports this contract.

The representation preserves passport/schema/template versions, identity, holder, issuer, verification metadata, competency categories, recursively nested subcategories, individual skill proficiency and framework, supporting credentials with issuer details, and evidence. Skills reference credentials/evidence by ID without flattening the competency hierarchy. Backend PDF generation should consume this same complete JSON tree after the contract is approved. Do not derive an authoritative passport from the dashboard's flat overview metrics.

`PassportPreview` is a neutral, expandable inspection of that structure, used on both the dashboard and passport page. It does not implement or approximate a final passport design. The old decorative passport card has been removed. The supplied blank and filled four-page PDFs have now been located and visually inspected. The unchanged blank template is available in the shared preview. Populated alignment and missing-field placement still require approval; see `docs/passport-template-integration.md`. No template or backend files were modified.

`src/data/passport.ts` is an explicitly unverified structural fixture, including a nested subcategory, skill, credential and evidence. Its taxonomy and proficiency scale are examples only. Demo inputs are always displayed as unverified even if their status field is accidentally set to verified. Only Django may supply authoritative claims. A public verification request must use the backend verification result, never this preview or a client-editable JSON object.

Before production integration, implement runtime schema validation, duplicate-ID and reference-integrity checks, and confirm proficiency codes, timestamps, schema migrations, PDF field mappings, permissions and public data minimization. Keep the TypeScript interface and JSON schema synchronized when the contract is finalized.

## Other frontend modules

- `src/pages.tsx`: existing student pages and verification form; admin pages are isolated in `src/admin/`.
- `src/data/mock.ts`: separate typed student demo data and loader.
- `src/services/api.ts`: private Axios client; the independent public verification adapter lives in `src/verification/service.ts` and uses inspected Django contracts.
- `src/i18n.tsx`: persistent English/Georgian locale; navigation and selected copy translated. Full translation remains pending.
- `src/components/ui.tsx`: shared cards, loading, error/empty presentations.

Verification never generates a mock authenticity result. PDF selection is local; explicit submissions use the public transport only after official-registry configuration is enabled. Current simulated backend sources are rejected. Profile preferences stay local and do not update official records. The future game remains at `/student/game`; game logic and offline caching are not implemented.

Configure production hosting to rewrite SPA paths to `index.html`. Confirm API origins, session cookies and Django CSRF handling before adding protected requests or mutations. API responses must be validated, and student query caches must be cleared on logout or account changes when sessions are integrated.

## Checks and outstanding dependencies

Architecture checks render route trees without a browser to verify denied access, role isolation, public independence, all student pages with synthetic test sessions, nested passport data and demo-status labeling. They do not replace browser/mobile interaction testing or real backend authentication tests.

Remaining dependencies: approved passport PDF/template and data contract; Django authentication and explicit administrator permissions; real student data; verification/upload/status endpoints; credential issuance and export; career frameworks; admin services and classroom sync. Finish Georgian translations, browser accessibility testing, and bundle splitting. Backend code remains unchanged.

## Local preview troubleshooting

Vite does not load `.env.example`. The ignored `frontend/.env.local` explicitly enables this checkout with `VITE_ENABLE_DEMO=true`. Restart the dev server after changing it. The startup output prints `Demo Preview ON` or `OFF`; with OFF, the real access guards intentionally block private pages. Use the localhost URL printed by `npm.cmd run dev`, not `npm.cmd run preview` or the generated `dist/index.html`.

`check:preview` uses jsdom with actual Vite environment loading, React effects and unseeded asynchronous mock queries. It checks both namespace entry redirects, Student/Admin dashboard content, chart component mounting, cross-workspace navigation, public Verification routes, disabled issuance and absence of network calls. It is a DOM integration check, not a browser screenshot or visual-layout test. `check:demo` separately forces the flag on for isolated safety tests and proves built artifacts cannot enable it.

## Preview acceptance routes

The Admin sidebar uses `/admin/course-mappings`, `/admin/classroom-sync`, and `/admin/audit-logs`. Older `/admin/courses`, `/admin/sync`, and `/admin/audit` URLs redirect with search/fragment preserved. `npm.cmd run check:preview` renders all requested Student/Admin/public pages using the actual local demo environment and unseeded mock queries. It checks chart SVG mounting, menu opening/navigation/closing, disabled official actions, React/DOM errors and zero API requests. This is DOM testing with mocked element dimensions; responsive visual layout and real browser console checks still require a connected browser.

## Passport template preparation

The shared `PassportPreview` is used at `/student/passport`, `/admin/passports/preview`, and `/admin/students/:id/passport`. It preserves the recursive presentation hierarchy and distinguishes internal Student UUID, external student ID, public Passport ID and public Passport Version ID. The source blank PDF is embedded unchanged as an explicitly unfilled reference; sample values are displayed separately. No QR codes, signatures or official credentials are generated. See `docs/passport-template-integration.md` for the exact field mapping, source evidence, schema v2 incompatibilities and required backend work.
