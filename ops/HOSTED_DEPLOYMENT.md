# Hosted deployment handoff — 2026-10-29

## Scope and repository state

Fixes are isolated in `AI-Skills-Passport-Hosted-Fix`, branch `fix/hosted-demo-navigation`, based on fetched `origin/main` at `daab29d`. No push, merge, production branch update, or Vercel change was performed. Existing worktrees and their files were preserved. Run `git log -1` in this worktree for the final implementation commit.

Fetched branch review: main includes the completed backend/frontend integration (`fa912b7`) plus routing/demo edits; integration ends at `fa912b7`. Existing frontend feature branches are earlier snapshots. `demo/vercel-preview` includes main but does not provide independent project/hostname safety. The compatibility worktree is an older baseline and was not used to replace integrated main.

## Causes and fixes

- `/` intentionally redirects to `/verify`; public verification had no links to either dashboard. Added responsive React Router links to its existing layout. Kept the original verification experience, branding, and passport-centered dashboard. No extra passport model or analytics section.
- Direct routes require SPA fallback. Kept that behavior, explicitly set Vite/build/dist, and excluded `/api` from the fallback. Without a backend proxy, API paths now fail rather than return the app HTML.
- Authentication contract error: private client uses `/api/`, not `VITE_API_BASE_URL`. A catch-all Vercel rewrite can answer `/api/accounts/me/` with HTML; that fails the strict Django contract. This explains the source-level failure mode. The actual deployed response was not inspected because no deployed URL/project session was supplied.
- `VITE_ENABLE_DEMO` alone cannot safely enable production previews. Main also contained a broad `BTU_DEMO_BUILD` escape hatch. Removed that escape hatch and added a dedicated hosted guard. Ordinary builds remain live, including when the old flag is set.
- Hosted demo requires an exact Vercel project ID, dedicated branch, vercel.app hostname, and no public API or Google client config. A copied/promoted artifact refuses to mount on any other hostname. An embedded CSP blocks network connections and form submission; demo Vercel headers add the same restriction. Project owners must still keep live/demo domains and secrets separate; code cannot prevent an owner from deliberately reconfiguring both projects.
- Both Axios transports were audited: private/session/CSRF calls reject demo traffic; public verification rejects lookups/uploads in demo. Student/admin demo providers use synthetic fixtures. Admin issue/revoke/import/sync actions reject; local Excel preview stays local. Live adapters are guarded by the shared client. No browser blockchain transaction provider was found.

## Dedicated demo deployment

After reviewing this branch, create a dedicated `demo/hosted-passport` branch at the approved commit and a NEW Vercel project. Do not repurpose the existing live project. Do not merge a demo-specific deployment config into production.

Project settings: Root Directory `frontend`; Framework `Vite`; Build Command `npm run build`; Output Directory `dist`; Node 24 (tested). Enable Vercel system environment variables so `VERCEL`, `VERCEL_PROJECT_ID`, and `VERCEL_GIT_COMMIT_REF` are available. Set this project's production branch to `demo/hosted-passport`.

On the demo branch only, copy `frontend/deployment/vercel.demo.json` over `frontend/vercel.json` before committing/deploying. Keep only its dedicated vercel.app domain. Disable production domain aliases and avoid attaching live secrets or integration credentials.

Set these build variables for the demo branch/project:

```dotenv
BTU_HOSTED_DEMO=true
VITE_ENABLE_DEMO=true
BTU_DEMO_PROJECT_ID=<exact NEW demo project's prj_... identifier>
BTU_DEMO_HOSTNAME=<exact-dedicated-demo-project>.vercel.app
VITE_PUBLIC_VERIFICATION_ENABLED=false
```

Leave `VITE_API_BASE_URL` and `VITE_GOOGLE_CLIENT_ID` absent/empty. Do not manually invent Vercel system variables. Never add database, mail, Google service-account, signing-key, or production credentials. Preview builds from other branches intentionally fail while hosted demo is enabled. Generated preview URLs intentionally refuse to mount unless they match the configured hostname; use the dedicated stable alias.

Redeploy after setting variables: Vite values are embedded at build time. Demo banner must remain visible. Public verification UI is available, but official verification is intentionally disconnected; synthetic records must never be shown as officially valid.

Local development remains `VITE_ENABLE_DEMO=true` followed by `npm run dev`. No hosted variables are needed locally.

## Live Vercel deployment (requires separate approval)

Keep the existing live project and approved production branch. Root Directory `frontend`, Framework `Vite`, Build Command `npm run build`, Output Directory `dist`.

```dotenv
BTU_HOSTED_DEMO=false
VITE_ENABLE_DEMO=false
VITE_API_BASE_URL=/api/
VITE_PUBLIC_VERIFICATION_ENABLED=true
VITE_GOOGLE_CLIENT_ID=<approved public Google Web Client ID>
VITE_PUBLIC_VERIFICATION_SOURCES=POSTGRESQL_CREDENTIAL_REGISTRY,POSTGRESQL_PASSPORT_REGISTRY,POSTGRESQL_DOCUMENT_REGISTRY
```

Remove obsolete `BTU_DEMO_BUILD` and demo-only project/hostname variables. No secrets may use a VITE_ prefix.

Use `frontend/deployment/vercel.live.example.json` as a reviewed template. Replace `REPLACE-WITH-DJANGO-HOST` with the actual HTTPS backend hostname. Its `/api/:path*` external rewrite must precede the SPA fallback and preserves the `/api/` prefix required by Django. API responses must never be cached. This is the missing private-auth connection; changing `VITE_API_BASE_URL` alone cannot supply it.

Recommended topology is browser -> same-origin Vercel `/api/` -> HTTPS Django. Keep Django session/CSRF cookies host-only, HttpOnly, Secure, SameSite=Lax. Do not weaken cookies or add wildcard CORS. Browser requests stay same-origin, so browser CORS middleware is unnecessary for this topology. Trust only known gateway headers and verify the forwarded Host/Origin/protocol on the actual platform before enabling proxy trust.

Vercel rewrite references: https://vercel.com/docs/routing/rewrites and https://vercel.com/docs/frameworks/frontend/vite . Dashboard Root Directory, branch assignment, environment scopes, aliases and existing overrides cannot be verified from this checkout; an operator must inspect them before publishing.

## Django hosting requirements

A static Vite deployment does not run the Django application. No public Django endpoint was supplied or proven available. Provision a persistent HTTPS Python web service, managed PostgreSQL with TLS, durable private passport/PDF storage, SMTP, and background workers. Use the pinned root `requirements.txt` and a Python runtime compatible with those pinned packages. Keep the web and worker on the same database and private storage. Generated student documents must not be published as static frontend assets.

Supply all production keys/settings from `backend/.env.example`, including independent `DJANGO_SECRET_KEY`, `AUTH_TOKEN_PEPPER`, `ACCOUNTS_OTP_HMAC_KEY`, `DATABASE_URL`, `DJANGO_DEBUG=false`, explicit `DJANGO_ALLOWED_HOSTS`, exact HTTPS `DJANGO_CSRF_TRUSTED_ORIGINS` for the live frontend, production SMTP settings, and matching `GOOGLE_OAUTH_CLIENT_ID`. Register the live HTTPS frontend as an authorized Google JavaScript origin and configure its university Workspace audience. Google Sheets credentials are separate, server-only, and require approved source profiles. Student and administrator records/grants must be provisioned through the existing institutional process.

From repository root in the backend release environment:

```sh
pip install -r requirements.txt
python backend/manage.py check --deploy
python backend/manage.py migrate --plan
# Review the migration plan and back up the real DB before the approved release.
python backend/manage.py migrate
# In a separately supervised worker process:
python backend/manage.py run_backend_workers
# In the web service (provider may require a different bind address):
gunicorn --chdir backend config.wsgi:application --bind 0.0.0.0:$PORT
```

Configure reverse-proxy TLS termination carefully; `DJANGO_TRUST_X_FORWARDED_PROTO=true` is appropriate only when the gateway overwrites that header. Include the actual host received by Django in allowed hosts, never `*`. The existing `ops/gunicorn.conf.py` binds loopback for a local gateway; managed hosting usually needs the explicit public bind shown above. Configure persistent storage and timeouts for PDF jobs. Run additional proof/publication workers per the existing blockchain runbook if real proof issuance is approved. Keep blockchain disabled until actual network, deployed registry, restricted signer file, and confirmation worker are validated. No schemas or contracts were changed by this fix.

## Validation and remaining release gates

Passed: TypeScript plus ordinary production build, hosted demo production build, lint; architecture, admin (including live adapter fixtures), verification, demo, passport, auth, student, passport-card, integration and spreadsheet checks; actual-config preview DOM routes; hosted build/project/branch/hostname/API/Google guards; browser passport layout at seven widths (375–1920), including all 33 variable-content pages.

New built-artifact Chromium checks passed at 390, 768 and 1440 pixels: seven direct paths and refreshes per viewport, landing navigation to all three areas, dashboard content, logo image loading, no overflow, zero API/external requests, no page errors, and wrong-host refusal. HTTPS demo origin is mapped to locally served built files by the test; no Vercel service is contacted. Live anonymous redirects passed with an explicitly synthetic HTTP 403 session fixture, not real authentication. Reports: `frontend/hosted-browser-results.json`, `frontend/hosted-regression-results.json`. Screenshots are local ignored files in `frontend/hosted-browser-artifacts/`.

`check:browser` requires an owned running Django synthetic test environment (`BTU_LIVE_TEST_ARTIFACTS` and browser tools), so real Django/Google/SMTP/database/spreadsheet/blockchain acceptance was not run. Actual Vercel edge routing, dashboard settings, project env scopes, cookies through its external rewrite, Google account selection, real issuance, and live verification remain unverified. No deployed URL or authenticated Vercel management tool was available. These are release gates, not claimed successes.

Before publishing: review this isolated commit, approve the dedicated demo branch/project, enter the real demo project ID/hostname and deploy there. Then test its stable HTTPS URL and all six requested refresh routes. Separately deploy/validate Django and the live proxy with actual session JSON, CSRF bootstrapping, allowed roles, login/logout, Google audience, cookie flags, and no API caching before approving any live deployment. Build warnings about chunks over 500 kB remain nonblocking.
