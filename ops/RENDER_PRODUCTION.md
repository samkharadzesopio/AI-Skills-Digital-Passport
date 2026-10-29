# Render production configuration and main integration

Target branch: `main`. This integration retains main `55e7201`, the reviewed
hosting package from `e06323c`, and public verification links to the real Student
and Administrator sign-in pages. It preserves the compact horizontal workspace
navigation, current session handling, and forced-live production builds.
The API rewrite preserves bare `/api`, trailing slashes and query strings;
the SPA fallback excludes API requests. API responses retain `private, no-store`
and disable Vercel rewrite caching. Existing worktrees, stashes and edits remain
intact. No live provider settings or shared database data are changed.

## Exact dashboard settings

| Setting | Value |
| --- | --- |
| Branch | `main`, after this candidate is reviewed and merged |
| Root Directory | **Leave blank** (repository root) |
| Runtime | Python |
| Python | `3.13.13`, pinned in root `.python-version`; remove a conflicting dashboard version override or set `PYTHON_VERSION=3.13.13` |
| Build Command | `bash ops/render_build.sh` |
| Start Command | `bash ops/render_start.sh` |
| Pre-Deploy Command | `python backend/manage.py migrate --noinput`, only after approving the Neon migration plan/backup |
| Auto-Deploy | Disable for this manual production rollout |

The proposed `backend` Root Directory excludes root `requirements.txt`, shared
`ops` configuration and root assets. Render does not make files outside a Root
Directory available. Do not use `pip install -r ../requirements.txt` with that
root. The suggested `gunicorn app:app` is not this Django application's entry point.

The build script installs root pinned requirements and collects static files; it
does not migrate a database. The start script enters `backend` and runs:

```bash
gunicorn --config ../ops/gunicorn.conf.py --bind "0.0.0.0:${PORT}" config.wsgi:application
```

`backend/config/wsgi.py` defines the actual `application`, defaulting to
`config.settings`. The script defaults a missing PORT to Render's standard 10000.
It preserves reviewed worker/time/header limits, no raw access logs, and disabled
control socket. It overrides the local-only loopback bind for Render ingress.
Do not copy the `backend/ $` dashboard display prefix into either command.

If the plan lacks a Pre-Deploy Command, schedule the approved migration as an
explicit one-off release step before sending traffic. Do not move migrations
into every Gunicorn startup or claim a build applied the schema. No Neon migration
was performed during preparation.

## Database release prerequisite

Read-only inspection on 2026-10-29 confirmed 48 applied migrations and 46 tables
in the configured Neon database. The current `main` code already contains 50
migrations. The two outstanding migrations are `accounts.0008_google_identity`
and `accounts.0009_workspace_portal`; this hosting/sign-in integration adds no
migration files and does not alter the existing ones.

The 48-migration schema lacks the Google identity/portal tables and the
`accounts_user.portal_only` column required by current authentication code.
It must receive a separately approved, backed-up migration rollout before this
version serves authenticated traffic. Do not treat a successful static build or
WSGI bootstrap as evidence that this release prerequisite has been completed.
The build and start scripts intentionally do not apply migrations.

## Environment variables on Render

| Exact name | Required value / operator input |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | Prefer unset (WSGI defaults to `config.settings`), or `config.settings`; never a test/local profile |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_ALLOWED_HOSTS` | Actual Render/custom backend hostname, without scheme/path; the current source target is `ai-skills-digital-passport.onrender.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Exact verified new Vercel HTTPS origin; add only approved actual preview origins; no current frontend URL is confirmed |
| `DJANGO_TRUST_X_FORWARDED_PROTO` | `true` behind Render's trusted HTTPS-terminating ingress; confirm header sanitization |
| `DATABASE_URL` | Private Neon PostgreSQL connection string; code requires SSL. Confirm actual project/role/connection permissions, migrations and schema in an approved release step |
| `GOOGLE_OAUTH_CLIENT_ID` | Approved Web Client ID, exactly equal to Vercel `VITE_GOOGLE_CLIENT_ID`; authorize the verified frontend origin in Google |
| `DJANGO_SECRET_KEY` | Stable independent private value, at least 50 characters |
| `AUTH_TOKEN_PEPPER`, `ACCOUNTS_OTP_HMAC_KEY` | Independent private values, each at least 32 characters |
| `ACCOUNTS_ACTIVE_STUDENT_STATUSES` | Exact approved nonempty comma-separated institutional statuses |
| `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD` | Real TLS transactional SMTP configuration; mail remains an implemented dependency |
| `DJANGO_DEFAULT_FROM_EMAIL` | Provider-authorized institutional sender |
| `DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_USE_TLS`, `DJANGO_EMAIL_USE_SSL` | For STARTTLS: `587`, `true`, `false` (existing defaults); use the provider's actual settings |
| `DJANGO_EMAIL_BACKEND` | Prefer unset, preserving `django.core.mail.backends.smtp.EmailBackend` |
| `PORT` | Render-supplied; do not hardcode a local development port |
| `WEB_CONCURRENCY` | Optional; existing Gunicorn default is 2, size for the selected instance and database connections |

No CORS package is configured or needed for the same-origin Vercel `/api/` proxy.
CSRF origin trust remains necessary when the external proxy presents the backend
Host. Keep Secure/HttpOnly/SameSite=Lax host-only cookies and JSON CSRF bootstrap.
Never use wildcard hosts, weaken cookie/CSRF policy, or enable test email bypasses.

The previous HTTP 400 does not establish a database failure. Incorrect Host
allowlisting reproduces 400 even on the CSRF endpoint, which does not prove DB
readiness. Check the actual deployed branch/SHA, `DJANGO_ALLOWED_HOSTS`, ingress
Host and sanitized application logs. Correct-host production bootstrap is tested
locally; the cause of the historic live response is not proven without live logs.
A fresh unauthenticated CSRF probe during this preparation timed out after 25
seconds without an HTTP response; live backend readiness remains unverified.

## Static files, issued PDFs and workers

WhiteNoise `6.12.0` serves only collected public static files with compressed
manifest storage. `STATIC_ROOT=backend/staticfiles`, `STATIC_URL=/static/`.
Generated static output is ignored by Git. React assets remain on Vercel.
WhiteNoise does not publish `MEDIA_ROOT` or Student PDFs.

Issued PDFs currently use filesystem `backend/media`. Provision persistent storage
for that exact deployed directory (or separately implement a reviewed storage
backend) before real issuance. Render's ephemeral filesystem alone is insufficient
for immutable issued documents across restarts. This change does not provision a
disk, change issued bytes, or regenerate missing issued PDFs.

Provision a separate trusted worker from the same reviewed branch/environment:
`python backend/manage.py run_backend_workers`. Its mail configuration is checked
before later recovery/publication work. Preserve the existing issuer, source and
proof policies. Configure actual approved Sheet targets/service-account storage
and any required blockchain registry/signer/confirmation worker separately.
Unconfigured proof must remain unavailable, never simulated as verified.

Student Google code is unchanged. Admin login remains the existing password and
explicit-permission flow; Admin Google login is not implemented in this checkout.
Real Google, SMTP, institutional provisioning and genuine verification still need
approved live accounts/data. See `SMTP_DEPENDENCY_AUDIT.md` for mail dependencies.

## Validation

The Linux-only `python -B ops/test_render_hosting.py` runs the exact build/start
scripts, checks Gunicorn imports `config.wsgi:application`, and tests production
HTTP/bootstrap, secure cookies, allowed-host 400, anonymous private API/CSRF
denials, actual collected CSS and media isolation. It refuses a private `.env`,
uses synthetic settings and never connects to a database/provider. Run it on an
isolated checkout/container because it collects generated static files.

`--wsgi-only` runs real production Django WSGI acceptance on Windows and explicitly
does **not** claim Gunicorn was exercised. A Linux GitHub Actions check is included
for pull requests; it installs the complete pinned dependencies and runs `pip
check` and the Gunicorn smoke test. The local Docker engine was stopped; no shared
engine or containers were started. Test outcomes and remaining gates are reported
with the delivery; no production-readiness claim follows from local fixtures.

Local evidence: exact installed versions of all pinned runtime requirements were
verified; production WSGI/static/security smoke passed with synthetic inputs;
Node 26 production build, lint, demo/auth/verification/architecture checks, and
all 24 compiled-frontend navigation cases passed. The official Vercel routing
compiler validated preserved API suffixes and private/no-store headers. The
selected disposable Django/HTTP/browser suite is recorded in the final delivery.
On this integration, 679 selected Django tests and 50 focused spreadsheet tests
passed, alongside system/migration checks and 7 actual Chrome journey groups with
78 API responses. The existing runner excludes two legacy reference-SQL comparison
tests. Final real Chrome/Django acceptance passed 6 journeys at 7 viewport sizes
with 83 API responses, including native PDF verification and secure logout. It
also verified the dashboard reserves space for the workspace navigation. Owned
resources were disposed. PostgreSQL records and provider/proof fixtures were
synthetic; local acceptance does not establish live provider or hosting readiness.

References: [Render monorepo roots](https://render.com/docs/monorepo-support),
[Render Django setup](https://render.com/docs/deploy-django),
[Python selection](https://render.com/docs/python-version),
[Gunicorn configuration](https://gunicorn.org/configure/).
