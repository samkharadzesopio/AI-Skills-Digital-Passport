# Frontend stabilization, 29 October 2026

Subsequent Render/main integration preserves this navigation and API-safe fallback,
adds the full-suffix API proxy to the supplied Render origin, retains no-store
headers, and disables demo in the Vite build configuration as well as npm's build
override. The no-proxy/legacy-config notes below describe the earlier reviewed
state. Current deployment instructions are in `../../ops/RENDER_PRODUCTION.md`;
the destination's live readiness still needs verification before rollout.

Integration worktree: `AI-Skills-Passport-Main-Stabilization`.
Branch: `integrate/frontend-stabilization-main-20261029`.
Main base: `daab29dc61eae22f0aa1c707cdc044ee3efa8b0c`.
Original reviewed commit: `f2365660c87532d6fb1e081e7461ea79877b214e`,
based on integration `fa912b7e09103a0e804e5c41cb090979a75cfdc9`.
The single add/add conflict in `frontend/vercel.json` retains SPA routing while
excluding API paths and adding the reviewed no-store policy. All seven main-only
commits remain ancestors; only the original nine frontend paths are changed.

The existing integrated frontend is retained. The visual reference is
`fix/frontend-blockchain-compatibility` at `faf2af4`. Its older live workspace
must not replace the integrated Student/Admin implementations. No passport
artwork, dashboard content, backend code, authentication or permissions changed.
The hosted-demo branch was reviewed as a reference only; none of its production
demo flags, host guards or network-blocking CSP are introduced into this branch.

## Changes

- Shared compact navigation to Student Dashboard, Admin Dashboard and Public
  Verification remains available on public, login, protected and outage screens.
- Authentication failures keep protected content unavailable, with retry and
  a sign-in link. A transport/contract error is never treated as anonymous or
  authenticated. Valid anonymous sessions retain the existing login redirects.
- Vercel SPA fallback handles direct frontend paths while excluding `/api`
  and `/api/*`. API responses are marked private/no-store. No backend address
  is assumed or hardcoded in the active deployment configuration.

## Vercel configuration after review and approval

- Use the approved stabilization commit, not `demo/hosted-passport`.
- Root Directory: `frontend`; Framework: Vite; install: `npm ci`;
  build: `npm run build`; output: `dist`.
- `VITE_ENABLE_DEMO=false`, `VITE_API_BASE_URL=/api/`,
  `VITE_PUBLIC_VERIFICATION_ENABLED=true`.
- Configure the institution-approved public `VITE_GOOGLE_CLIENT_ID`, matching
  Django's `GOOGLE_OAUTH_CLIENT_ID`. Register the actual frontend Google origin.
- Remove hosted-demo/legacy demo overrides. No secrets belong in `VITE_*`.
- The production build explicitly overrides `__BTU_LOCAL_DEVELOPMENT__` to false,
  including when both `VITE_ENABLE_DEMO=true` and `BTU_DEMO_BUILD=true` are set.
  Main's legacy Vite configuration is retained; use `npm run build` for releases.

The active `vercel.json` does not proxy API requests yet. A frontend deployment
alone will therefore not repair the known backend connectivity problem.
After the backend developer verifies the HTTPS destination, use
`deployment/vercel.live.example.json`, replacing its explicit hostname
placeholder with that verified host, as the reviewed `vercel.json`. Preserve
`/api/` and keep its external rewrite before the SPA fallback. Do not deploy
the placeholder. The previously supplied Render URL is not yet an approved,
working destination. Vercel settings, alias ownership and deployed commit still
require dashboard verification; no management connection is available here.

The private client intentionally remains same-origin `/api/`. Changing the
public `VITE_API_BASE_URL` cannot redirect private authentication requests.
Do not enable cross-origin cookies, wildcard CORS or an authentication bypass.

## Validation and limits

`npm run build` includes TypeScript checks. Run `npm run lint` and the existing
auth, architecture, demo, Student/Admin, verification, spreadsheet, passport
integration and passport-layout checks.

`npm run check:production-routes` runs Chromium against the compiled `dist`
artifact at 390, 768 and 1440 pixels, with isolated test-only API interception.
It checks direct dashboard navigation and refresh for authenticated, anonymous,
503-outage and malformed-session responses, public navigation and root redirect,
no horizontal overflow, no production demo banner, and no private dashboard
requests before authorization. Its local static server models the committed
SPA rewrite; it does not prove actual Vercel edge behavior.
The optional Playwright installation defaults to the existing temporary
`btu-passport-browser-tests` tools directory; `BTU_BROWSER_TOOLS` and
`BTU_BROWSER_EXECUTABLE` can select an isolated test installation/browser.

These fixtures are never imported by production application code. Passing
frontend tests does not establish real Google login, Django sessions, database
records, issuance, PDF downloads, Sheets, revocation or blockchain operation.
Real acceptance requires the approved backend, test accounts and test records.
No push, merge or deployment is part of this preparation.

## Backend handoff and release order

1. Backend owner verifies deployment identity, allowed hosts, HTTPS detection,
   PostgreSQL readiness and `/api/accounts/csrf/` plus anonymous session JSON.
2. Review the exact frontend commit and verified-origin rewrite together.
3. With deployment approval, deploy a staging frontend and inspect real edge
   routing, cache headers, cookies, CSRF and Student/Admin login/logout.
4. Test permitted dashboard operations using approved non-sensitive records.
5. Approve production promotion only after real authenticated acceptance.

Keep all existing worktrees and their unfinished edits intact.
