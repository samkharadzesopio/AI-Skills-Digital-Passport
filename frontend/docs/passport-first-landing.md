# Passport-first student landing

The latest landing-page request supersedes the earlier dashboard summary-card composition. `/student/dashboard` now presents only the interactive passport, minimal section navigation, accessible text reader and Download PDF, Share Passport and View History actions. Analytics, greeting, statistics and achievement previews have been removed from the landing page; their dedicated pages and navigation remain available.

Sizing follows the main content area excluding the sidebar, with a width/viewport-height constraint and unchanged landscape proportions. Desktop controls fit within the tested viewport; mobile uses normal document scrolling when needed. Styling is scoped to the student landing. The original passport artwork and pagination remain intact, including continuation pages for long records.

Live actions reuse existing authenticated PDF status/download and reference contracts. PDF availability and current-passport sharing guards remain authoritative. The history action opens the existing passport history section. Refresh remains in the live header. No-passport/unavailable states are explicit, and lifecycle/proof information remains visible in the compact passport. Demo download/share/history actions stay disabled and the Demo Mode banner remains visible. No backend, authentication, proof contract, administrator, import or public verification implementation was changed.

Validation: production build including TypeScript, Oxlint, all existing non-browser regression checks and Git whitespace checks passed. Authentication/route assertions were updated for the deliberate removal of dashboard identity/analytics text; profile and session-isolation checks remain. Product checks cover dashboard sharing, available/unavailable PDF actions, no-passport controls and history navigation.

The isolated Chromium layout check covers 1920x1080, 1440x900, 1366x768, 1280x720, 1024x768, 768x1024, 390x844 and 375x667 in Demo Mode, all four sections and a 33-page variable-content fixture. It asserts main-area centering, centered controls, desktop visibility and no internal/horizontal overflow. It also exercises the actual Live Mode React route with synthetic HTTP responses at six desktop/tablet/mobile sizes. Those are browser fixture tests, not real Django/PostgreSQL or chain end-to-end tests. Screenshots and reports are stored outside the repository in `%TEMP%/btu-passport-layout-results`.

Work remains uncommitted on `feature/frontend-backend-final-integration`, with no branch switch, merge or push. The original frontend checkout and its 49 preserved files are untouched.

## Actual running website diagnosis and verification cleanup

The old design at `localhost:5173` was not a cache problem. Both IPv6 PID 31564 and IPv4 PID 29540 serve `AI-Skills-Digital-Passport/frontend`, not this worktree. Actual HTTP source probes confirmed the old analytics component at localhost, 127.0.0.1 and ::1. These processes and the original checkout were preserved.

The corrected servers were started from `C:/Users/User/OneDrive/Desktop/AI-Skills/AI-Skills-Passport-Final-Integration/frontend`:

- Demo preview, PID 21108: `http://127.0.0.1:5174/student/dashboard` (`VITE_ENABLE_DEMO=true`).
- Live public interface, PID 37092: `http://127.0.0.1:5175/verify` (`VITE_ENABLE_DEMO=false`, public verification enabled with the existing PostgreSQL source allowlist).

Port 5173 intentionally still serves the older checkout. Use the above URLs to inspect the corrected work. No environment file or secret was copied. The corrected servers can be reproduced from this frontend directory using `npm.cmd run dev -- --host 127.0.0.1 --port 5174 --strictPort` with Demo Mode true, or port 5175 with Demo Mode false and the existing documented public verification configuration.

The public `/verify` route now renders the existing passport-identifier form directly, with its existing PDF upload route as a compact secondary link. The sample passport import, carousel and obsolete passport-landing styles are removed from public verification. Results remain allowlisted professional panels; no full passport is rendered. Existing request/loading/error/cooldown/cancellation, credential-free public transport, lifecycle/proof semantics and privacy restrictions are unchanged. The shared student passport component is retained.

The student sidebar now labels the landing route My Passport and the dedicated route Passport details, preserving both destinations without identical labels. Its decorative support card is removed and dashboard spacing is compacted. Passport sizing includes a fallback for the Demo banner height even if its measured CSS variable is not yet available; the landscape card and all controls are fitted without clipping or hidden content.

`node scripts/check-running-website.mjs` opens the operator-started URLs directly, not a replacement test server. It checks the student route and preview-free public form at 1920x1080, 1440x900, 1366x768, 1280x720, 768x1024 and 390x844. Desktop/mobile valid, invalid, revoked, replaced and unavailable public-result states use intercepted synthetic responses in isolated browser contexts only. The running Vite servers contain no synthetic success endpoints. Screenshots and `results.json` are under `%TEMP%/btu-actual-website-results`. Browser checks and visual screenshot inspection confirmed the separation of the two pages. Actual Django/chain success remains untested.

Additional touched source files for this cleanup: `verification/pages.tsx`, `verification/verification.css`, `artwork-theme.css`, `layouts/StudentLayout.tsx`, and student navigation labels in `live/ProductWorkspace.tsx`. `scripts/check-running-website.mjs` was added and the existing graphical check now asserts no public passport preview. All changes remain local and uncommitted.
