# Fresh Vercel / Render environment audit — 2026-10-29

Scope: `hosting-fix`, starting at `77645eddc621e3c9bddc78f573a32e3b3f057a29`.
Source inspection and local validation do not establish the live dashboard
configuration, the deployed commit, database health, or successful real Google login.
No private environment file or live provider setting is changed by this work.

The owner confirmed that hosting is being configured from scratch. The current
production frontend URL is **not yet confirmed**. The former `a3ux.vercel.app`
address below is historical probe evidence only; do not use it as a setup value.
No approved live test account identifiers or genuine public verification
references have been provided.

## Vercel environment variables

The only application variable needed for the current primary Student sign-in
screen is `VITE_GOOGLE_CLIENT_ID`. API routing and public verification work with
their source defaults. Values are strings, entered without shell quotes.

| Exact variable name | Required? | Correct value | Environment | Reason | Source file |
| --- | --- | --- | --- | --- | --- |
| `VITE_GOOGLE_CLIENT_ID` | Required for Google Student login | The approved OAuth **Web application Client ID**, exactly matching Render's `GOOGLE_OAUTH_CLIENT_ID`; ends in `.apps.googleusercontent.com` | Production; Preview when testing login; Development for local Google login | Missing/invalid ID disables the primary Student sign-in control. No Client Secret is used. The actual approved ID is not present in this checkout and must be obtained from the operator. | `frontend/src/auth/WorkspaceSignIn.tsx:10`, `frontend/src/auth/GoogleSignIn.tsx:15` |
| `VITE_ENABLE_DEMO` | Optional | `false`, or leave unset | Production and Preview; normally Development too | Default is off. Only a running development server can enable demo with the exact string `true` after the build guard correction. | `frontend/src/demo/mode.ts`, `frontend/vite.config.ts` |
| `VITE_API_BASE_URL` | Optional; conflicting if set to another origin/path | Prefer unset; explicit same-origin value is `/api/` | Production, Preview, Development | Controls **only public verification**, not login/private APIs. An absolute Render URL bypasses Vercel, needs CORS, and can make verification fail while private APIs work. An incorrect path routes verification incorrectly. | `frontend/src/verification/service.ts:7`, `frontend/src/verification/validation.ts:3` |
| `VITE_PUBLIC_VERIFICATION_ENABLED` | Optional | `true`, or leave unset | Production and Preview; Development for live verification | Enabled by default outside Demo Mode. Exact string `false` disables all public verification requests. | `frontend/src/verification/service.ts:10` |
| `VITE_PUBLIC_VERIFICATION_SOURCES` | Optional | Prefer unset; explicit value: `POSTGRESQL_CREDENTIAL_REGISTRY,POSTGRESQL_PASSPORT_REGISTRY,POSTGRESQL_DOCUMENT_REGISTRY` | Production, Preview, Development | These are the default exact serializer labels. An explicitly empty list disables verification. Wrong labels reject results; labels do not grant issuer trust or blockchain proof. | `frontend/src/verification/service.ts:8`, `frontend/src/verification/adapters.ts:4` |
| `VITE_API_URL` | Unnecessary | Do not add; remove if present as obsolete configuration | All | No usage anywhere in this frontend; it does not route authentication or verification. | Frontend-wide environment search; clients in `frontend/src/services/api.ts` and `frontend/src/verification/service.ts` |
| `BTU_DEV_API_TARGET` | Unnecessary for hosting; optional for local development | Leave unset on Vercel. Local default is `http://127.0.0.1:8000` | Development server only | Used by the Vite development proxy; never configures the static deployment. | `frontend/vite.config.ts:16` |
| `BTU_DEMO_BUILD` | Dangerous in the starting commit; unnecessary after correction | Remove from every Vercel scope if present | All hosted scopes | Previously enabled synthetic builds when combined with `VITE_ENABLE_DEMO=true`. The corrected Vite configuration ignores it. | Previous `frontend/vite.config.ts:12`; regression in `frontend/scripts/check-demo.mjs` |
| `NODE_ENV` | Unnecessary to add manually | Use the framework's production build default; remove a manual `development` override | Production and Preview | This is a standard build/tool variable, not a custom API selector. Both hosted scopes run a production build. | `frontend/package.json:8`; Vite environment/mode behavior |

`import.meta.env.DEV` and `BASE_URL` are Vite built-ins; do not create dashboard
variables with these names. `BASE_URL` supplies paths for brand/template assets,
not the backend. `__BTU_LOCAL_DEVELOPMENT__` is a compile-time define in Vite,
not an environment variable. No frontend runtime `process.env` API selector exists.

Other `process.env` reads in `frontend/scripts` are test harness inputs only:
`BTU_ADMIN_ARTIFACTS`, `BTU_ADMIN_FIXTURE`, `BTU_AUTOMATION_FIXTURE`,
`BTU_BROWSER_EXECUTABLE`, `BTU_BROWSER_TOOLS`, `BTU_E2E_FIXTURE`,
`BTU_E2E_MAILBOX`, `BTU_FRONTEND_DJANGO_FIXTURE`, `BTU_LIVE_TEST_ARTIFACTS`,
`BTU_LIVE_TEST_URL`, `BTU_REVIEW_READY`, `BTU_TEST_ARTIFACTS`,
`BTU_TEST_VITE_CACHE`, `BTU_VERIFICATION_FIXTURE`, and `BTU_VISUAL_OUTPUT`.
They do not belong in Vercel hosting configuration.

Vite embeds `VITE_*` values in public JavaScript at build time. Configure these
before a fresh build. Never put Neon credentials, Django secrets, SMTP passwords,
Google service-account material, or signing keys in these variables.

## Render settings compatible with this frontend

These are the exact **environment names the existing Django code reads**, not
generic Django setting names to paste into Render.

| Exact Render variable | Requirement / safe value | Why / source |
| --- | --- | --- |
| `DJANGO_DEBUG` | `false` | Enables production secure cookies and HTTPS redirect; `backend/config/settings.py:43,146-164`. |
| `DJANGO_ALLOWED_HOSTS` | `ai-skills-digital-passport.onrender.com` for the normal external rewrite Host; add only exact additional hosts if the real proxy forwards those as Host | Comma-separated hostnames, without scheme/path. `USE_X_FORWARDED_HOST` is not enabled, so a browser host in `X-Forwarded-Host` does not require an allowed-host entry. No wildcard. `backend/config/settings.py:44`. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | The exact **verified new frontend HTTPS origin**, obtained from the new Vercel deployment; append approved Preview origins comma-separated. No literal value is available yet. | The browser uses the Vercel origin while the external rewrite normally presents Render as Host. This proxy mismatch needs CSRF trust even though browser traffic is same-origin. Never use the historical URL, localhost, or broad preview wildcards for production. `backend/config/settings.py:55`. |
| `DJANGO_TRUST_X_FORWARDED_PROTO` | `true` when Render's trusted ingress supplies/sanitizes `X-Forwarded-Proto: https` | Django must recognize terminated HTTPS or it can redirect API requests. Confirm the trusted proxy contract; clients reject redirects. `backend/config/settings.py:163`. |
| `GOOGLE_OAUTH_CLIENT_ID` | The same approved Web Client ID as `VITE_GOOGLE_CLIENT_ID` | Server validates audience, signature, nonce, verified BTU email and `hd=btu.edu.ge`. Missing or mismatched IDs block Google login. `backend/config/settings.py:122`, `backend/apps/accounts/google_auth.py`. |
| `DATABASE_URL` | Existing private Neon PostgreSQL connection string, supplied securely | Django requires it and uses `dj_database_url.config(ssl_require=True)`. No database URL belongs on Vercel. Live credentials/connectivity/migrations were not inspected or changed. `backend/config/settings.py:113`. |
| `DJANGO_SECRET_KEY` | Existing private, independently generated value, at least 50 characters | Required at startup outside development; keep stable for sessions. `backend/config/settings.py:39,194`. |
| `AUTH_TOKEN_PEPPER` | Independent private value, at least 32 characters | Production startup requirement. `backend/config/settings.py:183,192`. |
| `ACCOUNTS_OTP_HMAC_KEY` | Independent private value, at least 32 characters | Production startup requirement, including for a Google-only frontend. `backend/config/settings.py:184,198`. |
| `ACCOUNTS_ACTIVE_STUDENT_STATUSES` | Exact institution-approved, nonempty comma-separated status values | Production startup requirement. Do not invent the institution's accepted statuses. `backend/config/settings.py:185,200`. |
| `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD`, `DJANGO_EMAIL_USE_TLS`, `DJANGO_EMAIL_USE_SSL`, `DJANGO_DEFAULT_FROM_EMAIL` | Approved SMTP settings only on Render. Typical STARTTLS settings are port `587`, TLS `true`, SSL `false`; actual provider/credentials/from-address must be confirmed. | Default production SMTP requires a host and TLS or SSL; cannot enable both. Email OTP/recovery also needs the appropriate delivery workers. `backend/config/settings.py:166-182`. |
| `DJANGO_EMAIL_BACKEND` | Normally leave unset to use `django.core.mail.backends.smtp.EmailBackend` | Do not select local file/console/test mail to claim working production email. `backend/config/settings.py:166`. |

There is no installed CORS package, CORS middleware, or environment reader in the
current backend. Adding `CORS_ALLOWED_ORIGINS` to Render would have no effect in
this checkout. Browser requests to relative `/api/` on Vercel do not need CORS.
Cross-origin verification overrides change that fact and should be removed.

Session and CSRF cookies are HttpOnly, SameSite=Lax, and Secure with
`DJANGO_DEBUG=false`; cookie domains remain host-only using Django defaults.
These cookie settings are code settings, not environment readers. Keep cookies
on the browser's Vercel host through the proxy; no cross-site SameSite=None policy
is needed. The frontend gets a masked token from `/api/accounts/csrf/` JSON and
sends `X-CSRFToken` for private mutations, with credentials included. Public
verification deliberately omits cookies/CSRF/authorization.

Keep existing server-side integrations on Render: `GOOGLE_SERVICE_ACCOUNT_FILE`,
`BTU_GOOGLE_SHEET_ID`, `BTU_SPREADSHEET_GOOGLE_SOURCES_JSON`,
`BTU_AUTHORIZED_COMPLETION_SOURCES`, `VERIFICATION_TRUSTED_ISSUER_REFERENCES`,
`PASSPORT_IDENTITY_EVIDENCE_SOURCES`, and the actual `PASSPORT_BLOCKCHAIN_*`
readers in `backend/config/settings.py:302-314`. Correct frontend registry labels
cannot make an unavailable or unconfirmed blockchain proof positive.

## API and build configuration findings

Private authentication, Student, and live Admin services use
`frontend/src/services/api.ts`: fixed `/api/`, credentials included, CSRF bootstrap,
15-second timeout, and redirects rejected. An environment variable cannot
redirect that client to Render. Public verification defaults to `/api/`, omits
credentials, uses a 30-second timeout, and rejects redirects. Its optional
`VITE_API_BASE_URL` accepts arbitrary HTTPS origins, so an absolute Render value
can bypass the rewrite. There is no automatic synthetic fallback on API failure.

The starting rewrite `/api/:path*` fails to match trailing-slash requests under
Vercel's routing compiler (`@vercel/routing-utils` 6.6.1). For example,
`/api/accounts/csrf/` and `/api/accounts/google/challenge/` select the SPA fallback
instead of Render. Without the final slash the rewrite reaches a slashless Django
path, which can redirect; these clients reject redirects.

The corrected source `/api/:path(.*)` and destination
`https://ai-skills-digital-passport.onrender.com/api/:path` preserve the complete
API suffix, including trailing slashes. The API rule stays before the SPA
fallback. No `trailingSlash: false` setting is added. Vercel's unset default does
not add slash-normalization redirects. The Render destination is the supplied
production backend, not a development URL, and is independent of Vite variables.

Fresh project settings:

- Root Directory: `frontend` (confirm in Vercel; not expressible by this nested file).
- Framework: Vite.
- Node.js Version: `24.x`, a currently supported Vercel LTS version satisfying
  locked Vite's `^20.19.0 || >=22.12.0` engine range. A second clean local build
  passed on official Node `24.22.2`; check the actual Vercel build log too.
- Install Command: `npm ci`, using committed `frontend/package-lock.json`.
- Build Command: `npm run build` (`tsc -b && vite build`).
- Output Directory: `dist`.
- Do not reuse a previous build cache for the first deployment after configuration.

Framework/install/build/output are now explicit in `frontend/vercel.json`.
Vite's local `/api` development proxy is not included in a static deployment.

Demo defaults off. The starting build guard allowed the exact pair
`BTU_DEMO_BUILD=true` and `VITE_ENABLE_DEMO=true` to enable synthetic dashboards
in any build. This was reproduced by compiling and evaluating the demo module.
The corrected guard enables Demo Mode only for a running development server;
all static builds, including Vercel Preview, use Live Mode. The demo regression
sets both legacy flags and `NODE_ENV=development` to exercise the accidental-build
case. Demo sessions never become real authenticated identities.

## Deployment scope and external checks

`hosting-fix` is confirmed as the local branch and was fetched independently from
`origin/hosting-fix`. Git alone cannot identify the Vercel environment. By default,
a non-production branch receives Preview variables, but the project can assign
`hosting-fix` as Production or track it through a custom environment. Check the
actual deployment's Environment, Branch, and commit SHA in the dashboard. A
`vercel.app` URL alone does not establish any of these.

Production: approved Google Client ID and live defaults above. Preview:
configure the variables for that environment, using a branch-specific override
for `hosting-fix` if appropriate. Each preview origin used for login must also be
approved in Django's CSRF list and the OAuth client's Authorized JavaScript
Origins. Current rewrites send **all hosted scopes to the same Render backend**;
a Vite API variable does not select a separate backend for private Preview
traffic. Development: local Vite proxy/local Django, with demo enabled only if
explicitly wanted. Google origin entries must match the exact local origin.

Google's live console must contain the **verified new frontend HTTPS origin**
(no path/trailing slash), plus each approved actual Preview origin. The current
production origin remains unconfirmed; do not register the historical URL as a
substitute. The primary screen uses Google FedCM in a
supporting browser; the separate linking component uses GIS. Neither flow uses a
Client Secret or redirect URI from a frontend environment variable. Real Google
consent/audience/Workspace access remains an external configuration check.

Read-only public HTTP observations during this audit: the supplied Vercel root,
`/api/accounts/csrf/`, and `/api/accounts/csrf` returned HTTP 404. A later root
request exposed Vercel's `x-vercel-error: DEPLOYMENT_NOT_FOUND`. A direct Render
CSRF GET first timed out after 20 seconds, then returned HTTP 400 with an HTML
content type on retry. This is not the expected HTTP 200 JSON bootstrap. Inspect
the actual Render deployment/logs and `DJANGO_ALLOWED_HOSTS`; the HTTP status
alone does not establish the cause or database connectivity. No login,
verification lookup, real student data, or Neon connection was used in these
probes. The supplied Vercel URL and the Render bootstrap are live acceptance
blockers, independently of the source corrections.

## Local validation

- Fresh `npm ci` from the existing lockfile: 161 packages installed; no package
  manifest or lockfile changes. A dedicated package cache was used for this run.
- Removed only the verified generated `frontend/dist` directory; the dependency
  reinstall also removed old TypeScript/Vite caches under `node_modules`.
- `npm run build`: passed, using explicit live settings and `NODE_ENV=production`.
  The existing large-JavaScript-chunk warning is non-fatal.
- Follow-up clean production build on official Node `24.22.2`: passed after
  deleting generated `dist` and forcing TypeScript recompilation. The Node
  executable was downloaded from `nodejs.org` and verified against its published
  SHA-256 manifest. System Node and application dependencies were unchanged.
- `npm run lint`, `check:architecture`, `check:demo`, `check:auth`,
  `check:verification`, `check:student`, `check:admin`, `check:spreadsheet`: passed.
  Authentication, Student, Admin, verification and spreadsheet checks use local
  contract/DOM/transport fixtures; they do not establish live service success.
- Vercel's own `@vercel/routing-utils` 6.6.1 accepted the transformed configuration;
  13 implemented API paths retain their complete Render path and 8 frontend paths
  select the SPA fallback. Validator tooling is in a run-owned directory outside
  the checkout, not a new application dependency.
- Production artifact inspection rejects known demo fixture markers and confirms
  Google, Student passport and public verification API paths remain compiled.
- Actual `config.settings` and CSRF middleware checked in an isolated Python
  process with synthetic environment values and `.env` loading disabled: trusted
  forwarded HTTPS, required database SSL, secure session flags and a Secure,
  HttpOnly, SameSite=Lax host-only CSRF cookie passed. Missing token, untrusted
  origin, and absent proxy-origin trust were all rejected. No database/network
  connections were made by this configuration check.
- Follow-up `python -B ops/run_isolated_tests.py --frontend-django`: passed with
  a fresh owned loopback PostgreSQL cluster, test-only settings, synthetic
  records, and local mail. Django system/migration checks and **239 selected
  Django tests** passed. The Google-read gate, ownership/cleanup and local-dev
  guard tests passed too.
- Actual local HTTP acceptance passed: spreadsheet **13 requests**, Student
  **64 proxied requests**, Admin **146 proxied requests**, and public verification
  **35 proxied requests**. Those drivers use jsdom, real local Django APIs and
  PostgreSQL; provider/proof fixtures remain synthetic. These exercised sessions,
  CSRF/ownership/grant denials, records, issuance/revocation, QR/reference/PDF
  verification, Excel import/replay/history, and honest provider-unavailable
  responses. Public cancellation checks logged two `ECONNRESET` messages while
  the verification suite completed successfully.
- Actual Chrome/React/Django acceptance passed: **7 journey groups / 79 API
  responses**, synthetic PostgreSQL awards and PDFs, with no API interception.
  This does not cover real Google, chain proof or production services. The runner
  confirmed owned database/media/server cleanup and removal of its PG cluster.
- The first follow-up attempt stopped because the shared Python environment
  lacked the already-declared `web3==7.13.0` dependency; owned cleanup passed.
  The successful retry supplied that dependency in a run-owned directory using
  process-local `PYTHONPATH`. The shared environment, requirements and application
  lockfile were not modified. Isolated browser tooling also stayed outside Git.

No real authorized Student/admin credentials or approved genuine public
verification reference were supplied. Live dashboards, Neon access, real login,
real Passport/QR/PDF operations, real spreadsheet imports and confirmed on-chain
proofs remain unverified. This delivery is not a production-readiness claim.

Still confirm in the live dashboards:

1. Correct Vercel project/domain, `frontend` Root Directory, production branch or
   custom branch tracking, exact deployed commit, and build/output overrides.
2. Environment-variable scopes and branch-specific overrides; no stale demo flag,
   absolute verification base, disabled verification flag, or empty source list.
3. A fresh build with the correct variables; Vite values require rebuilding.
4. Render's deployed branch/commit, normal `config.settings`, trusted forwarded
   HTTPS, exact hosts/origins, private Neon TLS connection, migrations, and workers.
5. Through Vercel: JSON CSRF bootstrap with a Secure/HttpOnly cookie, successful
   real Google login/session restore and logout, and public verification without
   cookies, redirects, or an HTML SPA response. Test issued proof only with an
   approved public reference. Local tests do not establish this live behavior.

## Manual dashboard setup for the new production deployment

1. Import `samkharadzesopio/AI-Skills-Digital-Passport` into the intended Vercel
   project/account. Set Root Directory to `frontend`; choose Vite, `npm ci`,
   `npm run build`, and `dist`. The tracked configuration supplies the last four.
   In Build and Deployment, select Node.js Version `24.x`.
2. For the requested production release from this branch, manually set Production
   Branch / Production environment Branch Tracking to `hosting-fix`. Confirm that
   the deployment actually targets Production. If it remains a Preview branch,
   configure Preview values for `hosting-fix` instead; Production values do not
   automatically apply. The live branch mapping has not been inspected or changed.
3. In the selected deployment environment, enter the approved public Web Client ID
   as `VITE_GOOGLE_CLIENT_ID`, matching Render's `GOOGLE_OAUTH_CLIENT_ID`. Optional
   explicit live values are `VITE_ENABLE_DEMO=false`,
   `VITE_PUBLIC_VERIFICATION_ENABLED=true`, and `VITE_API_BASE_URL=/api/`.
   Prefer leaving `VITE_PUBLIC_VERIFICATION_SOURCES` unset to use the exact code
   defaults. Remove stale `BTU_DEMO_BUILD`, `VITE_API_URL`, absolute API-base
   overrides, hosted `BTU_DEV_API_TARGET`, and a manual development `NODE_ENV`.
4. Start a fresh deployment of the reviewed `hosting-fix` commit with the previous
   build cache disabled. Read the actual generated URL/custom domain from that
   deployment and verify reachability. Record this URL as the new frontend origin;
   it cannot be inferred from a repository name or an old deployment.
5. Manually add that exact origin to Render's
   `DJANGO_CSRF_TRUSTED_ORIGINS` and the OAuth client's Authorized JavaScript
   Origins. Confirm the Render-only settings above, normal production settings,
   private Neon TLS connectivity, migrated schema, and required workers. The
   previously observed Render HTTP 400 requires operator diagnosis before login
   can be accepted; inspect logs and the exact allowed hostname.
6. After configuration, verify `/api/accounts/csrf/` through the new frontend
   returns JSON and a secure cookie without redirects or SPA HTML. Then use
   explicitly approved test accounts and genuine public references for the real
   Student/admin, Passport/QR/PDF, verification, and spreadsheet journeys. Until
   those inputs are provided and the journeys pass, live acceptance is blocked.

All dashboard actions above are operator instructions. This change does not
create a Vercel project, change branch tracking, configure either provider, deploy
the application, or read production database records.

Reference documentation:
[Vercel rewrites](https://vercel.com/docs/routing/rewrites),
[Vercel configuration](https://vercel.com/docs/project-configuration/vercel-json),
[Vercel environment scopes](https://vercel.com/docs/environment-variables),
[Vercel branch tracking](https://vercel.com/docs/git),
[Vercel Node.js versions](https://vercel.com/docs/functions/runtimes/node-js/node-js-versions),
[Vite environment behavior](https://vite.dev/guide/env-and-mode),
[Django CSRF origins](https://docs.djangoproject.com/en/5.2/ref/settings/#csrf-trusted-origins).
