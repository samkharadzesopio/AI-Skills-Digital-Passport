# Accounts, authentication, and authorization

## Identity model

`accounts.User` is Django's configured authentication model. The unique,
case-normalized BTU email is the login identity. Passwords use Django's password
hashers; Student sign-in uses the preserved email OTP contract, while password
authentication is restricted to explicitly provisioned administrators. Production
settings require a generated `DJANGO_SECRET_KEY`, a separate `AUTH_TOKEN_PEPPER`,
and an independent `ACCOUNTS_OTP_HMAC_KEY`. Student academic fields remain in `students.Student`.
`User.student` is nullable for pre-link and administrator accounts, UUID-backed,
protected from deletion, and one-to-one at the database level. Administrators do
not require a Student row. Superuser accounts are intentionally disabled.

There is no public account claim operation. An OTP can provision an account only
when a pre-existing Student row has an approved active status and its stored BTU
email matches the OTP address. The caller cannot choose a Student UUID or external
student ID. An administrator with the explicit
`accounts.manage_student_accounts` permission creates a one-time invitation for a
pre-existing Student. The recipient email is taken from the Student record, and
only its keyed digest and a keyed invitation-token digest are stored. The email
token expires after 24 hours and can be redeemed once. Registration accepts the
invitation token and a password; it has no Student UUID or email ownership input.
Registration marks the email verified because the one-time token was delivered to
the pre-provisioned Student email. An administrator re-invites by rotating an
expired or revoked invitation. Student OTP login verifies the mailbox before
starting a session. A trusted, unverified administrator can establish a restricted
password session to access account status and email verification; private and
administrative API permissions require email verification.

## Session API

All paths are prefixed by `/api/accounts/`:

| Method | Path | Access |
| --- | --- | --- |
| GET | `csrf/` | Public CSRF token bootstrap |
| POST | `login/` | Administrator password login, CSRF required |
| POST | `otp/request/` | Public generic student login request, CSRF required |
| POST | `otp/verify/` | Public one-time student OTP login, CSRF required |
| POST | `logout/` | Session, CSRF required |
| GET | `me/` | Authenticated |
| GET | `student-status/` | Authenticated; linked/unlinked only |
| POST | `register/` | Public invitation redemption, CSRF required |
| POST | `password/change/` | Authenticated, CSRF required |
| POST | `password/reset/request/` | Public, generic response, CSRF required |
| POST | `password/reset/confirm/` | Public OTP completion, CSRF required |
| POST | `email/verify/request/` | Authenticated, CSRF required |
| POST | `email/verify/confirm/` | Authenticated, CSRF required |
| POST | `admin/student-invitations/` | Explicit admin permission, CSRF required |

The browser obtains a masked token from `csrf/`, sends it as `X-CSRFToken` on
state-changing requests, and uses same-origin session cookies. Session cookies are
HttpOnly, Secure outside local development, SameSite=Lax, and expire after 30
minutes or when the browser closes. The CSRF cookie is HttpOnly; the bootstrap endpoint returns the masked token
for the frontend to keep in memory. Logout flushes the server session. Django's
session authentication rechecks active status and the password session hash on
each request, so disabled accounts and password resets invalidate old sessions.
The Student OTP flow marks the mailbox verified before starting a session. The
separate email verification endpoints support trusted pre-created unverified
accounts. The global private API permission rejects unverified accounts.

## OTP and rate limits

OTP values use `secrets`, expire after five minutes, and are never written in
plaintext. PostgreSQL stores only keyed HMAC verifiers, keyed email/IP identifiers,
attempt counters, expiry, and consumption time. Student login codes use the
upstream `LoginChallenge` table; email verification and recovery use
`OTPChallenge`. Verification locks the active row, counts invalid attempts, and
consumes a correct or exhausted code in the same transaction. A partial unique
index permits at most one unconsumed recovery/verification code per email and
purpose. Resend replaces the previous code. Persistent, row-locked account and IP
buckets are shared by all Django workers. SMTP delivery runs outside database
transactions; a login code remains unusable until delivery succeeds.

Defaults are 5 verification attempts, 3 OTP requests per account per 15 minutes,
20 OTP requests per IP per 15 minutes, 10 login attempts per account per 15
minutes, and 30 login attempts per IP per 15 minutes. No OTP, invitation token,
password, or submitted document content is logged by account code. Recovery
requests return the same response for unknown and eligible accounts.

OTP and rate-limit rows need periodic retention cleanup. The
`purge_expired_auth_state` command removes expired challenge rows and old counter
buckets; it does not remove invitations or accounts.

## Student and administrator authorization

`get_authenticated_student_id(request.user) -> UUID` returns the Student UUID
stored on an active, authenticated, email-verified Student-role account. It never
accepts an ID from request data and rejects an unlinked account, invalid
association, or Student status outside `ACCOUNTS_ACTIVE_STUDENT_STATUSES`. The
session backend fetches the user and related Student in one joined query; object
ownership checks reuse that validated user object for the current request.

Reusable permissions include `IsStudent`, `IsOwnStudent`, `IsOwnPassport`,
`IsOwnCredential`, `IsOwnPassportDocument`, and `IsAdminWithPermission`. Student
profile retrieval scopes the query to the linked Student and returns 404 for a
different Student identifier. Admin checks require all of: active account,
administrator role, staff status, and the exact Django permission. `is_staff`
alone never grants administrative access. Superusers are rejected by the policy.

Custom administrator permissions are `access_admin_api`, `manage_student_accounts`,
`view_student_records`, `manage_credentials`, `revoke_credentials`,
`sync_classroom`, and `import_completions`. The `bootstrap_admin` management
command creates the first least-privilege administrator and requires an explicit
permission list. Later permission changes are made through trusted operations
that update Django `user_permissions` or group membership.

Credential revocation policy is exposed at
`apps.accounts.authorization.authorize_credential_revocation` and configured as
`CREDENTIAL_REVOCATION_AUTHORIZER`. It requires `accounts.revoke_credentials` and
returns a stable `account:<UUID>` audit reference. The current
`feature/integration-verification` branch has no Credential model/service, so the
credential owner must connect this hook when that module is integrated.

## Deployment configuration

`settings.py` fails fast when production `DJANGO_SECRET_KEY`,
`AUTH_TOKEN_PEPPER`, `ACCOUNTS_OTP_HMAC_KEY`,
`ACCOUNTS_ACTIVE_STUDENT_STATUSES`, or `DJANGO_ALLOWED_HOSTS` are missing.
The active Student statuses must be supplied as exact comma-separated values
confirmed by the Student/integration owners. Wildcard hosts are
rejected. Production also requires HTTPS trusted origins, redirects HTTP to HTTPS,
sets secure session and CSRF cookies, enables `nosniff`, denies framing, sets a
same-origin referrer policy, and starts HSTS with a one-hour max age. HSTS
subdomains and preload remain explicit operator choices. `SECURE_PROXY_SSL_HEADER`
is set only when `DJANGO_TRUST_X_FORWARDED_PROTO=true`; enable it only behind a
trusted proxy that replaces the forwarding header.

Email uses SMTP by default. Configure `DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT`,
`DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD`, `DJANGO_EMAIL_USE_TLS`, and
`DJANGO_EMAIL_USE_SSL`, and `DJANGO_DEFAULT_FROM_EMAIL` through the deployment
environment. Production SMTP must specify a host and use TLS or SSL. There is no CORS
middleware or wildcard CORS setting. No Redis or process-local authentication
state is required.

`accounts.0001_initial` is Developer 2's existing migration and remains unchanged.
`0002` adds the account/invitation/recovery schema and preserves the original
case-insensitive uniqueness and student-link constraints. `0003` normalizes legacy
emails, assigns explicit roles, marks OTP-linked students and staff as verified,
and demotes legacy superusers. `0004` adds the stricter role and BTU email checks;
`0005` adds PostgreSQL identity immutability triggers. The data backfill and DDL
constraints are separate migrations to avoid PostgreSQL pending-trigger-event
errors while upgrading. Review existing account rows and confirm there are no
non-BTU login emails before applying the BTU-domain constraint. Also confirm the deployment has no prior
`auth.User` table or foreign keys before switching `AUTH_USER_MODEL`. Do not apply
these migrations to the shared Neon branch as part of this change. All migration
and concurrency tests use `config.auth_test_settings`, which accepts only the
explicit loopback PostgreSQL test host and never reads Neon settings.
