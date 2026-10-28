# Design, Demo Mode, and Vite restoration — 2026-10-28

Branch: `feature/frontend-visual-updates`; restoration base: `96ec681`. The restoration was prepared locally without merging or cherry-picking. No backend/blockchain modification occurred. Publication status is recorded in Git history.

## Cause and recovery

The later Pink + Orange design existed as uncommitted files in the original `AI-Skills-Digital-Passport` checkout, after `565d2c1`. A new worktree created from Eli's integration correctly omitted those uncommitted changes and the ignored `.env.local`. Consequently, its supported Demo Mode was off and its dashboards required real Django authentication.

The original checkout was only read. Its existing visual stylesheet was recovered into this worktree and imported after the existing artwork theme. Entire old authentication, workspace, routing, service, or verification components were not copied. Eli's `StudentShell`, `PassportLanding`, history routes, role/capability guards, typed services, proof binding, retry paths, credential/version deep links, PDF transport, and result facts remain intact.

Recovered presentation includes proposed magenta/orange interface tokens, larger height-aware passport, compact demo strip, narrower sidebar, compact header, light institutional login panels, official BTU logos, and verification forms directly on the public landing. Existing reference/upload components gained optional embedded presentation; submission handlers, normalization, request arguments, cancellation, file validation, rate limits, and proof/result semantics remain unchanged. Standalone verification routes still work. No passport artwork or official assets changed.

## Local hosting and demo

Confirmed the old PID 33908 was Vite in this new worktree before stopping only that process. Restarted Vite in the same frontend directory, PID 32368, strict port 5173, host localhost. Terminal output confirms Demo Preview ON. PostgreSQL, Django, Anvil, and unrelated processes were not stopped.

Local-only ignored `frontend/.env.local` now contains the existing supported setting `VITE_ENABLE_DEMO=true`, without secrets. No authentication bypass was introduced: the existing dev-only compile-time guard controls preview, production builds disable it, and real API services reject demo use. Live authentication behavior is unchanged. To return to Live Mode later, set that flag false and restart Vite; the missing approved Django configuration must still be supplied.

Open **http://localhost:5173/student/dashboard**. `/student/login` and `/admin/login` offer the existing “Open demo workspace” entry. `/verify` renders the recovered public interface but clearly reports official verification unavailable in Demo Mode.

## Verified behavior

Actual running-server Chromium navigation covered:

- Student dashboard and `/student/passport` redirect to it.
- All four passport section controls and keyboard page navigation.
- My Skills, using fictional sample competencies.
- `/student/history` to `/student/passport/versions`, displaying the explicit no-issued-demo-history state.
- Skills Gap Analyzer Coming Soon.
- Student and administrator login pages, with demo entry and no claim of authentication.
- Public verification forms and demo/service warnings.

Across these demo visits, recorded **zero `/api/` requests and zero browser page errors**. Download, sharing, issued-history action buttons remain disabled because sample passports are not issued records. Navigation to the history empty state remains available through Eli's sidebar. No real blockchain, academic record, or Django session operation was triggered.

Actual measured demo passport viewport: 749.52 × 529.95 px at 1366 × 768; 900 × 636.36 px at 1440 × 900 and 1920 × 1080; 736 × 520.39 px at tablet 768 × 1024; 358 × 253.13 px at mobile 390 × 844. Desktop passport/actions fit without document scrolling. Text access expands naturally. Original aspect ratio is preserved.

Screenshots and measurements: `frontend/restoration-review/after/`, with `student-dashboard-1366.png`, `student-dashboard-1440.png`, `student-dashboard-1920.png`, `student-dashboard-768.png`, `student-dashboard-390.png`, and corresponding student-login/admin-login/verify images. The dashboard screenshot was visually inspected.

## Validation

- `npm.cmd run build`: PASS, including TypeScript; existing approximately 789 kB bundle warning.
- `npm.cmd run lint`: PASS.
- PASS: `check:architecture`, `check:admin` (including live admin synthetic checks), `check:verification`, `check:demo`, `check:preview`, `check:passport`, `check:auth`, `check:student`, `check:passport-card`, `check:integration`, `check:passport-layout`.
- `node scripts/check-visual-restoration.mjs after`: PASS at all five required viewport sizes, including login/public rendering with synthetic anonymous session responses, focus, input/upload errors, four-page navigation, and zero API calls during demo navigation.
- `git diff --check`: PASS, with line-ending normalization warnings only.

Initial build caught an imported logo not used because a Unicode replacement did not match; fixed by targeting the existing logo markup. Initial architecture test caught the omitted “No login required” label; restored the existing translated label instead of weakening its test. Both checks were rerun successfully. No regression tests were deleted.

The separate `check:browser` real-service acceptance driver was not run: it requires a prepared owned Django/PostgreSQL/Anvil environment and test artifacts. Current evidence uses synthetic backend responses and fictional demo records; it does not prove real OTP delivery, production login, stored PDF generation, or chain confirmation.

## Changed files and remaining blockers

Tracked modifications: `src/App.tsx` (theme import), `src/auth/LoginPages.tsx` (logo only), `src/layouts/VerificationLayout.tsx` (logo only), and `src/verification/pages.tsx` (embedded form presentation).

New files: `src/btu-interface.css`, `scripts/check-visual-restoration.mjs`, this report, and local `restoration-review/` screenshots/measurements. `.env.local` is ignored. Build output remains ignored. Original checkout and previous branches/worktrees are preserved.

For publication, only the four tracked presentation files, stylesheet, browser test, and this report are included. Local configuration, generated screenshots/measurements, dependencies, and build output are excluded. A fresh development checkout must explicitly set `VITE_ENABLE_DEMO=true` in its own ignored `.env.local` and restart Vite to use the demo. The default and production behavior remain Live Mode.

Live service blockers remain the missing approved Django secret/database/OTP configuration, authenticated PostgreSQL access, and unavailable real Django/Anvil services. These do not prevent the explicitly fictional demo dashboard. No real-service readiness or merge approval is claimed.
