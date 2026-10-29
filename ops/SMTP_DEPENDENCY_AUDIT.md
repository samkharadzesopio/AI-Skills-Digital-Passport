# SMTP dependencies and authentication — 2026-10-29

Inspected `hosting-fix` at `08eac802ab3ea6941a09e8ceeafbb77e2cb3a8ed`.
Decision: retain SMTP. It is an implemented dependency, not unused configuration.
No runtime code, authentication, permissions, frontend or environment files are
changed by this audit. No credentials or live account data were inspected.

## Immediate findings

- Student Google sign-in is implemented and does not send email. Google-signed
  identity claims, including verified email and the BTU Workspace domain, are
  validated by the backend. This is distinct from sending an email code.
- **Administrator Google sign-in is not implemented in this checkout.** The Admin
  screen uses email/password; `AdminPasswordBackend` accepts only the approved
  staff ADMIN identity with no Student linkage and excludes superusers. The
  Google handler returns STUDENT portal identities and never grants Admin access.
  Supporting Admin Google login is a separate unmet product requirement; changing
  SMTP variables cannot implement it. Google authentication is left unchanged.
- Existing Admin password login and trusted `bootstrap_admin` provisioning do not
  require an outgoing code or invitation email. Provisioning sets verified status
  through the trusted management operation and requires explicit permissions.
- The application cannot simply drop SMTP settings: normal production startup
  requires an SMTP host/TLS, and the rollout preflight requires the SMTP backend.

## Feature impact

| Feature | Uses SMTP? | Required for production? | Impact if removed |
| --- | --- | --- | --- |
| Student Google login | No direct dependency | Required primary Student login | Google exchange itself needs no SMTP; removing the required SMTP host can prevent the entire backend starting. The optional legacy Google-link flow requires a fresh email-OTP login. |
| Admin Google login | Not implemented | Requested requirement currently unmet | SMTP changes cannot provide it; no Admin OAuth flow exists to preserve or claim tested. |
| Student password login | Not supported by the active authentication backends | Not the current Student login | Registration can set a password, but the Student backend accepts no password authentication; do not advertise this as a working alternate login. |
| Admin password login | No direct dependency | Required current Admin login | Existing eligible Admin sessions/password login do not send codes; backend startup and recovery dependencies still apply. |
| Password reset | Yes | Required to preserve implemented recovery | Eligible verified non-portal accounts, including Admins, cannot receive recovery codes. Requests normally enqueue durable mail. |
| Email verification | Yes | Required for the implemented email-verification workflow | Explicit verification messages cannot be delivered; failed codes are invalidated. Google token verification remains independent. |
| Account activation | Depends on path | Preserve implemented provisioning and access controls | New Google portal principals need no invitation email. Invitation-based Student registration depends on delivered invitation tokens; institutional academic linkage remains independently authorized. |
| Admin invitations | No Admin-account invitation feature found | Admins are provisioned through trusted management | The similarly named `/api/accounts/admin/student-invitations/` sends **Student** invitations created by an authorized Admin; those messages require SMTP. |
| Passport verification | No direct dependency | Required public service | Lookup/upload verification sends no mail; backend startup and worker dependencies can still affect availability/publications. |
| Notifications | No general notification mail found | No additional implemented notification dependency found | No passport, issuance/revocation or administrative alert mail sender was found. Authentication/provisioning mail remains necessary. |
| Student email-OTP login | Yes | Preserve implemented alternate service and legacy linking | Requests/delivery cannot operate normally without approved TLS SMTP and the mail worker. |

## Complete implemented delivery paths

All application delivery calls are Django `send_mail` with a bounded connection;
no separate `smtplib`, `EmailMessage`, `EmailMultiAlternatives`, or frontend email
provider integration was found.

| Path | Implementation | Delivery behavior |
| --- | --- | --- |
| Student login codes | `backend/apps/accounts/persistent_otp.py:130` | Production requests enqueue LOGIN jobs; codes are activated only after successful delivery. Configuration requires the exact SMTP backend, TLS/SSL, sender, secure sessions, approved statuses and HMAC key. |
| Email verification codes | `backend/apps/accounts/services.py:171` | Sends directly; failed delivery invalidates the code and the API returns a delivery error. |
| Password-reset codes | `backend/apps/accounts/services.py:238` | Production requests enqueue RESET jobs; the delivery path sends email and invalidates codes on failure. Google portal-only accounts are excluded from requesting password recovery. |
| Student invitation tokens | `backend/apps/accounts/services.py:309`, `views.py:300` | Admin permission is required; delivery failure revokes the invitation and returns 503. This is not an Admin invitation. |
| Background delivery | `backend/apps/accounts/mail_queue.py`, management commands `deliver_auth_mail` and `run_backend_workers` | Durable LOGIN/RESET outbox, bounded retries, no stored plaintext codes/provider exception bodies. |

`services.send_verification_email` is a compatibility helper with no external
caller found; the active explicit verification API calls
`send_email_verification_code` directly. The Django settings and mail dependencies
are used by the active paths above; they are not safe cleanup candidates.

Important worker coupling: `run_backend_workers` calls `deliver_one()` before
spreadsheet recovery and Passport refresh/publication work. `deliver_one()` checks
SMTP configuration **before** it looks for a queued job. Invalid/disabled SMTP
configuration therefore causes the combined cycle to fail before those later
tasks, even with an empty mail queue. A transport failure with otherwise valid
configuration is handled by the outbox retry path. Do not disable mail by choosing
console, file, dummy or in-memory delivery in production.

## Render configuration and initial deployment

There is no verified SMTP-free configuration preserving every implemented
production workflow. Student Google and existing Admin password login have no
intrinsic mail requirement, but that alone does not establish a fully functional
SMTP-free deployment. Removing the host under the default backend prevents normal
production startup; a non-SMTP backend fails the OTP/preflight/worker checks.

Keep or replace these Render values with the transactional provider's real
configuration. Gmail App Passwords are not required by the application protocol.

| Exact variable | Action |
| --- | --- |
| `DJANGO_EMAIL_HOST` | Keep; enter the real provider SMTP hostname. Required with the default production backend. |
| `DJANGO_EMAIL_HOST_USER` | Keep/replace with provider SMTP username where authentication is required. |
| `DJANGO_EMAIL_HOST_PASSWORD` | Keep/replace with provider SMTP credential; never commit or expose it. |
| `DJANGO_DEFAULT_FROM_EMAIL` | Use a provider-authorized institutional sender. Omit only if the existing `no-reply@btu.edu.ge` default is authorized. |
| `DJANGO_EMAIL_PORT` | Set the provider port; may be omitted if it is the existing default `587`. |
| `DJANGO_EMAIL_USE_TLS` | STARTTLS providers: `true` (already the default). |
| `DJANGO_EMAIL_USE_SSL` | STARTTLS providers: `false` (already the default). Never enable both TLS and SSL. |
| `DJANGO_EMAIL_BACKEND` | Prefer unset, retaining `django.core.mail.backends.smtp.EmailBackend`; do not substitute a test backend. |

Retain `GOOGLE_OAUTH_CLIENT_ID`, `VITE_GOOGLE_CLIENT_ID`, independent Django/OTP
keys, approved Student status policy, secure cookies and permissions. None is an
SMTP credential. No mail setting belongs in Vite's public variables.

Production-compatible option with the existing code: a paid Render service plus
Amazon SES TLS SMTP, a verified sending identity/domain, regional SMTP credentials,
and production sending access when sending to unverified recipients. No personal
Gmail account or Gmail App Password is needed. Provider onboarding and DNS/identity
verification remain operator tasks; delivery is not tested here.

Render Free web services block outbound ports 25, 465 and 587; Render blocks port
25 for all services. Confirm the actual service tier before relying on SMTP.
An HTTPS email API would need an explicitly reviewed implementation because the
current OTP and preflight code enforce the SMTP backend. It is not a drop-in
environment-variable workaround.

Sources: [Render Free restrictions](https://render.com/docs/free),
[Amazon SES TLS](https://docs.aws.amazon.com/ses/latest/dg/security-protocols.html),
[SES verified identities](https://docs.aws.amazon.com/ses/latest/dg/verify-addresses-and-domains.html).

## Validation and delivery boundaries

`python -B ops/run_isolated_tests.py --google-auth` passed on a fresh owned
loopback PostgreSQL cluster: **112 accounts tests**, **4 Google configuration
helper tests**, production-read gating/resource-safety tests, Django system checks,
and migration drift checks. Accounts coverage includes Admin password login and
explicit authorization, Student Google sessions and denial of Admin privileges,
OTP/mail failure handling, verification, recovery and invitation behavior.
Google signatures and email delivery use synthetic test fixtures; no real message
or Google sign-in was attempted. The runner confirmed owned-resource cleanup.
Real Google, real SMTP delivery, live Admin/Student access and Render/Neon remain
unverified. No live test accounts or genuine public references were provided.
No frontend code changed, so no new frontend build is required for this audit.
