# Local Student authentication

Open **http://127.0.0.1:5173/student/login**. Django is at **http://127.0.0.1:8000**; browser requests use Vite's existing same-origin `/api` proxy. A bare backend root URL returning 404 is normal: Django exposes API routes, not the React page.

## Cause of the reported error

The existing listeners were an older backend worktree and the audit frontend snapshot. The OTP POST `/api/accounts/otp/request/` returned **500**, specifically `Explicit ACCOUNTS_ACTIVE_STUDENT_STATUSES required.` The frontend correctly mapped this server failure to “Authentication service is unavailable.” CSRF GET was 200 and anonymous `/me/` was 403, which is expected and is handled as signed out.

The current worktree's ignored `.env` also had a blank active-student policy, a process-local memory email backend with no usable SMTP settings, and a local PostgreSQL URL while normal settings require database SSL. Its configured database connection failed with “server does not support SSL, but SSL was required.” PostgreSQL itself was running and the named local database was reachable without SSL; it had no Student records. Vite's existing proxy implementation was correct.

## Safe local setup

`config.local_dev_settings` is an explicitly selected development profile. It requires all of:

- `BTU_LOCAL_DEVELOPMENT=1` and `DJANGO_DEBUG=true`.
- PostgreSQL on `127.0.0.1`, `localhost` or `::1`, with the exact database name `btu_passport_local`.
- An explicitly configured active-student policy. This local synthetic database uses `ACCOUNTS_ACTIVE_STUDENT_STATUSES=ACTIVE`.

Only that profile permits non-SSL local database traffic and writes email to `backend/.local-mail`. It keeps real OTP generation/validation, expiry, single-use codes, rate limits, eligible Student identity, database sessions, PostgreSQL row locks, ownership, CSRF and exact permissions. Normal `config.settings` and production TLS/SMTP rules are unchanged. No CORS wildcard, anonymous login endpoint, fabricated session or administrator grant was added. Both development services bind only to 127.0.0.1.

The ignored backend `.env` was updated only to set the local ACTIVE policy. Its keys/passwords were not printed or committed. The existing database migrations were current; no schema migration or shared/Neon change was needed. Runtime logs/process metadata and the local mailbox are ignored by Git.

## Start or restart

From this integration worktree, with local PostgreSQL already running:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ops/start_local.ps1
```

This changes execution policy only for that script process, not the machine. Supply `-Python C:\path\to\venv\Scripts\python.exe` if the existing sibling virtual environment is elsewhere. Install locked dependencies in frontend with `npm.cmd ci` first. The launcher refuses occupied ports, checks Django configuration/migration consistency, starts hidden Django/Vite processes from this worktree, and probes both API routes before reporting readiness. It never migrates or seeds a shared database.

Stop old development listeners before restarting; do not stop unrelated PostgreSQL services. Launcher PIDs are in `backend/.local-run/processes.json`, and listener PIDs can be inspected with `Get-NetTCPConnection -LocalPort 8000,5173 -State Listen`. On Windows the virtualenv Python launcher may have a child Python process owning port 8000; stop that development listener as well when restarting. Logs are in `backend/.local-run`.

## Sign in locally

A clearly labelled synthetic Student record **local.student@btu.edu.ge** was created in `btu_passport_local`, external ID `LOCAL-DEVELOPMENT-STUDENT`. No credential, administrator account or session was seeded. It starts with empty academic records. The User/session is created only after successful real OTP verification.

1. Open the Student login URL and request a code for **local.student@btu.edu.ge**.
2. Open the newest email file in **backend/.local-mail** and enter its six-digit code in the page. Files are a local mailbox, not delivery to a real university inbox.
3. Codes expire after five minutes and work once. Resend is subject to the existing cooldown/rate limits; request a fresh code rather than reusing one consumed by a smoke test.

Other addresses still require a matching active canonical Student record. Unknown/inactive addresses receive the normal generic 202 response without a usable code. For a real university inbox, configure approved TLS SMTP, secure deployment cookies/HTTPS and institutional Student data through normal settings; no SMTP credentials or university API access were supplied here.

## Verification performed

Against the actual running services through port 5173: Student page 200, CSRF 200, anonymous `/me/` 403, missing-CSRF OTP POST 403, OTP request 202 with actual file delivery, incorrect code 400, valid code 200, authenticated `/me/` and Student dashboard 200, reused code 400, logout 204 and subsequent `/me/` 403. Invalid administrator credentials returned 401. No OTP values or secrets were printed.

Configuration boundary tests reject implicit activation, DEBUG=false, remote databases, wrong database names, SQLite and connection-option host/service overrides, and verify production configuration is not mutated. **466 backend tests passed in 113.641 seconds** (468 discovered; the runner's same two legacy SQL comparisons were explicitly excluded), including the three new boundary tests. Frontend auth/architecture checks, production build and lint passed. Django system checks, existing migration consistency and migration-drift checks passed; the final launcher also passed its direct/proxied readiness probes. No schema changes were made.

Local database/file delivery does not establish live SMTP or production readiness. The local profile sends development login mail synchronously, so no auth-mail worker is required for this setup.
