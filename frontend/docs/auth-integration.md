# Phase 7A authentication integration

## Implemented URLs

- `/student/login`: university email -> OTP request -> six-digit verification -> session restoration.
- `/admin/login`: email/password login. The registered Django serializer accepts `email`, not username.
- `/student/*`: Live Mode requires `/me/` to report a verified, linked STUDENT account.
- `/admin/*`: Live Mode remains denied until explicit backend permission capabilities are available.
- `/verify/*`: public, with no session bootstrap or login requirement.

All existing Demo Mode dashboards, sample data, hierarchical passport previews and original-template integration remain available when `VITE_ENABLE_DEMO=true`. Demo login pages display a link to the sample workspace and never mount authentication hooks or submit credentials.

## Exact inspected Django contract

The implementation was based on `backend/apps/accounts/{urls,views,serializers,authentication,permissions,persistent_otp,otp_utils}.py` and the root URL configuration. Backend files were read only.

- `GET /api/accounts/csrf/` returns `{csrfToken}` and sets the HttpOnly CSRF cookie.
- `GET /api/accounts/me/` returns `{email, role, email_verified, student_association}`. Role is `STUDENT` or `ADMIN`; association is `linked` or `unlinked`. No user UUID, Student UUID, external student ID or permission list is returned.
- `POST /api/accounts/otp/request/` takes `{email}` and returns HTTP 202 `{detail}`. Its response is deliberately generic, including ineligible or throttled requests; the UI never promises delivery. The frontend uses a 60-second resend cooldown and handles explicit HTTP 429 separately.
- `POST /api/accounts/otp/verify/` takes `{email, code}` with a six-digit code. HTTP 200 `{detail}` establishes the Django session; HTTP 400 represents invalid/expired/otherwise rejected codes. The frontend restores identity through `/me/` rather than trusting a success string as a user object.
- `POST /api/accounts/login/` takes `{email, password}` without trimming the password. HTTP 200 returns the account summary. Invalid credentials may return 400/401; HTTP 429 is rate-limited.
- `POST /api/accounts/logout/` returns HTTP 204. Only this successful response is treated as confirmed server logout.

SessionAuthentication may return HTTP 403 for anonymous `/me/`; the session adapter treats 401/403 on that endpoint as anonymous. A 403 on a mutation is not treated as a successful login/logout and does not trigger an automatic retry. HTML CSRF failures, network errors, timeouts, malformed contracts and server errors are handled without exposing raw server/request objects.

## Cookies, CSRF and cache lifecycle

The private Axios client is fixed to same-origin `/api/`, sends browser-managed session cookies, disables fetch caching and rejects redirects. It refuses absolute external request URLs. Passwords, OTPs and identity are never saved in localStorage, sessionStorage or URL parameters. The CSRF token is held only in module memory; raw Axios errors containing credential payloads are converted into small safe error codes before reaching UI state.

Every unsafe request first obtains a CSRF token from the JSON endpoint and sends it as `X-CSRFToken`. Concurrent token bootstraps share one request. Login rotates Django's token, so the in-memory token is discarded after successful OTP/password authentication. The next write (including logout) obtains a fresh token. Failed 403 checks also discard the token, but the user must explicitly retry; credential-bearing POSTs are never replayed automatically.

Successful authentication cancels old account queries, clears query caches, restores `/me/`, then caches the returned summary. Session queries restore after refresh and refetch on focus/reconnect. Logout clears private caches immediately, then clears session state after server confirmation. If logout fails, the UI explicitly says the server session may remain active and allows retry; it does not claim the cookie/session was destroyed. The session identity is not retained after the last session observer is removed.

## Development and production routing

The Vite dev server proxies `/api/*` unchanged to `http://127.0.0.1:8000`, preserving Host/Origin (`changeOrigin:false`) so Django can perform same-origin CSRF checks. Start Django separately with the approved local test configuration. Set `VITE_ENABLE_DEMO=false` in `frontend/.env.local` and restart Vite to exercise Live login pages. Keep it true for the mock preview. Private auth traffic intentionally does not use an arbitrary cross-origin `VITE_API_BASE_URL`.

Production hosting must route `/api/*` to Django and serve the SPA separately on the same origin. The Vite dev proxy is not included in a static production deployment. Django's allowed hosts, HTTPS/forwarded-origin settings and session/CSRF cookie policies must be configured by the backend operator; no CSRF exceptions, secure-cookie weakening, CORS wildcard or test-account provisioning was added.

The inspected persistent OTP flow requires configured active-student statuses, HMAC configuration, trusted university records, PostgreSQL row locking, database sessions and secure SMTP/cookie configuration. Do not disable those checks just to make an HTTP demo login succeed. Use an approved backend test configuration/local HTTPS where necessary.

## Backend dependencies and deliberate Live Mode limits

1. `/me/` exposes no explicit administrator permissions. A frontend `ADMIN` role never grants an admin capability. Login/session restoration work, but admin management remains on an authenticated dependency screen. An agreed server capability contract is needed before the frontend can check the exact permission for each operation. No missing field or route has been invented.
2. Live Student pages now use `/api/student/dashboard/` and the existing identity-scoped APIs; `/me/` does not need to expose a Student UUID. Dashboard/profile/skills/achievements/credentials/Passport/history display actual backend records. Demo Mode remains separate.
3. Current and historical Student PDF actions are connected. Admin directory/catalog/mapping, issuance, import and sync remain separate work. See `../../ops/STUDENT_INTEGRATION.md` for the current DTO adapters and acceptance evidence.
4. Unverified/unlinked/wrong-role accounts are denied the requested workspace. Email verification and account provisioning/recovery flows beyond the six requested endpoints are not added in this phase.
5. Subsequent Student acceptance passed real HTTP OTP/session/records/PDF/logout/ownership checks through Vite with disposable PostgreSQL and synthetic mail. Live SMTP and institutional access remain unverified.

## Validation and test classification

- `npm.cmd run check:auth` uses actual React components, routing, query state and an Axios adapter with synthetic Django-shaped responses. It covers exact payloads, CSRF header/bootstrap/rotation, OTP request and bad/valid codes, invalid password, refresh/expired session, missing permissions, rate limits, safe error conversion, confirmed/failed logout, no secrets in browser storage and absence of academic/admin data calls. **These are mocked integration tests, not real Django login tests.**
- `check:architecture` verifies Live guard behavior and independent public routes with synthetic sessions.
- `check:preview` verifies real local Demo Mode environment loading and mock page rendering without API requests.
- `check:demo` verifies direct auth calls are refused in Demo Mode and built artifacts cannot enable the mode.
- Build, lint, Admin, Verification and Passport checks remain required.

No graphical browser visual/keyboard test is claimed by these DOM/adapter checks. The separate `ops/test_student_e2e.py` covers real server cookies/APIs through the proxy; see the Student milestone report. The auth unit test now allows the scoped dashboard call after login.
