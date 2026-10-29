# BTU frontend visual redesign — 2026-10-28

Local review only. Branch `fix/frontend-blockchain-compatibility`, HEAD `565d2c1`. No commit, push, merge, branch switch, reset, or stash was performed. The pre-existing untracked `critical-fixes-test-results.json` is preserved. No backend, authentication service, verification service, proof adapter, official asset, or passport artwork was modified.

## Design changes

`src/btu-interface.css` defines reusable interface tokens for the proposed magenta #E50071, orange #FF7200, white, soft #F8F5F6, charcoal #292929, borders, shadows, and muted text. These are interface choices, not independently certified BTU brand specifications. The original passport retains its separate artwork colors and proportions. Pink is used for primary actions, navigation selection, page selection, and keyboard focus; orange remains predominantly inside the original passport and service-warning treatment.

The student shell now has a 216 px sidebar and 44 px header. The redundant Workspace/Overview breadcrumb was replaced with the actual page label. The existing intended navigation remains, with a Coming Soon badge for Skills Gap Analyzer. Demo disclosure is a compact white strip with all three original warnings and explicit links to sample workspaces. It still says the user is not authenticated and official actions are disabled.

The passport is centered with a maximum width of 900 px and height-dependent sizing. Controls sit immediately below it. Page status and the read-as-text disclosure share a row on desktop; the disclosure expands naturally and can introduce scrolling. No content or essential actions were clipped to meet the collapsed desktop fit. Small screens use natural scrolling and the full-width passport; text access remains available when small artwork lettering needs a readable alternative.

Student and administrator login retain their existing forms, session restoration, OTP/password behavior, cooldowns, errors, CSRF, and role checks. Shared CSS replaces the oversized dark panel with a balanced soft-neutral institutional panel and white form, magenta actions, consistent inputs and official BTU logo. Mobile stacks the panels. Demo login still opens an explicitly unauthenticated sample workspace.

Public verification now presents both existing reference and upload forms directly on its landing page, side by side on desktop and stacked on mobile. Embedded variants suppress redundant back links and repeated service notices. A single service-unavailable warning remains prominent above both forms. Standalone reference, PDF, QR, and results routes remain supported. Input/file validation, request cancellation, status parsing, source trust, public transport, and result logic were not changed. There is no sample passport or certificate selector.

Administrator pages inherit shared button/navigation/border styling; no major administrator redesign or management behavior change was made. Live student passport CSS also increases the existing card's available width while allowing its real record/PDF/proof controls to flow naturally.

## Measured dashboard improvements

Measurements are actual Chromium CSS-pixel bounding boxes of the demo passport viewport, captured with the same fixture before and after:

- 1366 × 768: **543.05 × 383.97 → 749.52 × 529.95 px** (38% wider). After redesign, essential actions end at approximately y=743; document height is 768 px.
- 1440 × 900: **729.72 × 515.95 → 900 × 636.36 px** (23% wider). Actions end at approximately y=862; document height is 900 px.
- 1920 × 1080: **900 × 636.36 → 900 × 636.36 px**. The previous large-screen card already reached the intended maximum. Actions end at approximately y=952; document height is 1080 px.
- Tablet 768 × 1024: 736 × 520.39 px. Mobile 390 × 844: 358 × 253.13 px, with stacked labels/actions and an expandable text view.

Aspect ratio remains the original 841.89:595.276. At the shortest desktop size, approximately 750 px is the practical balance between artwork readability and keeping all controls and warnings visible. Long records retain pagination; opening the full text alternative deliberately allows scrolling.

## Screenshots and reproducible evidence

Relative to `frontend`, `visual-review/before/` and `visual-review/after/` each contain full-page PNGs for these pages at widths 1366, 1440, 1920, 768, and 390:

- `student-dashboard-<width>.png`
- `student-login-<width>.png`
- `admin-login-<width>.png`
- `verify-<width>.png`

Each directory includes `measurements.json`. Desktop dashboard, student login, public verification, and mobile dashboard screenshots were visually inspected. The before verification page measured 1264 px tall on desktop; the new reference field and PDF selector are now visible in the first screen. The final verification page is about 939 px tall at 1366/1440; its footer and, on short screens, part of the upload action require natural scrolling. At 390 px it is about 1475 px tall, compared with 2005 px before. Mobile administrator login is about 948 px tall; scrolling is intentional.

Run `npm.cmd run check:visual-redesign` to recapture after screenshots. The script requires the same isolated Playwright/Chromium installation used by the existing passport-layout test in the temporary `btu-passport-browser-tests` directory. It runs a demo dashboard and Live Mode login/public pages with intercepted anonymous session responses. It never submits real credentials or creates backend records. To capture a baseline before editing, run `node scripts/check-visual-redesign.mjs before`.

## Validation

All existing checks passed: `check:architecture`, `check:admin`, `check:verification`, `check:demo`, `check:preview`, `check:passport`, `check:auth`, `check:product`, `check:public-transport`, `check:compatibility`, `check:passport-card`, and `check:passport-layout`.

`npm.cmd run build` passed, including TypeScript `tsc -b`. `npm.cmd run lint` passed. The existing approximately 730 kB main-bundle warning remains. Build/lint and verification/preview checks were rerun after the embedded-form refinement. The pagination browser check was rerun after the final dashboard sizing refinement.

The new visual browser check passed for 1366 × 768, 1440 × 900, 1920 × 1080, 768 × 1024, and 390 × 844. Assertions cover desktop passport/action fit, increased size, absence of horizontal overflow on all four pages, all four passport section controls, keyboard page navigation, visible focus, invalid reference feedback, and rejection of unsupported upload files. Existing pagination tests exercise all 33 long-content pages, touch behavior, reduced motion, and internal overflow checks across seven viewports.

During iteration, browser assertions caught actions below the fold caused by demo CSS import precedence, followed by excessive vertical spacing. These were corrected with scoped style specificity and a shared status/text-access row. A temporary assertion of exactly 750 px was adjusted to 749 px tolerance for the measured 749.52 px subpixel layout; the full fit assertions remain. An initial script-writing command used a duplicated frontend path and created no file; the corrected script is present. No regression tests were removed.

Existing tests use synthetic Axios responses, jsdom, and a fixture HTTP server. Browser snapshots use demo records and synthetic anonymous session responses. No actual Django/PostgreSQL, OTP delivery, issued PDF, import/revocation, or blockchain end-to-end acceptance is claimed.

## Files and remaining work

Modified tracked files: `package.json`, `src/App.tsx`, `src/layouts/StudentLayout.tsx`, and `src/verification/pages.tsx`. New source/test/report files: `src/btu-interface.css`, `scripts/check-visual-redesign.mjs`, and this report. `visual-review/` contains local screenshots, measurements, and validation logs. `dist/` was rebuilt and remains ignored. All changes are uncommitted.

Remaining dependencies: real Django/PostgreSQL acceptance, finalized proof-contract confirmation, inspection of the live authenticated dashboard with a real issued record, and integration conflict review. No real-service visual fit is certified by demo measurements. The existing proof/share eligibility restrictions remain unchanged. The reviewed screenshots contain no observed clipping or horizontal overflow; smaller screens retain natural vertical scrolling. The frontend remains **not approved for merging**.
