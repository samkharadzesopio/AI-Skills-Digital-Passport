# Phase 1 accounts handoff (pending shared integration)

Implemented on `feature/integration-verification`. Shared `config/settings.py`,
`config/urls.py`, Student permissions, and Developer 1's models/migrations are unchanged.
No shared Neon connection, migration, push, merge, or deployment was performed.

## Findings and migration decision

- `students/models.py`: canonical UUID primary key, case-sensitive external ID,
  unique case-insensitive university email; `student_status` is free text, not an enum.
  Developer 1 must confirm the exact status values eligible for login.
- Student migrations `0001_initial` and `0002_external_student_id_normalization`
  do not reference auth. Skill migrations reference Students, not an auth user.
- `accounts/authentication.py` was empty; no accounts migrations existed.
- Shared settings omit contenttypes/auth/sessions/accounts, session and auth
  middleware, and use empty DRF authentication classes. Its scaffold SECRET_KEY
  and console-style mail configuration are unsuitable for this login service.
- A custom `accounts.User(AbstractUser)` is compatible with the checked-in graph.
  This does NOT prove that changing AUTH_USER_MODEL is safe on an existing Neon DB.
  Developer 1 must review migration history and existing auth data before enabling it.
  If auth.User migrations/data are already in use, stop: adapting a separate
  one-to-one account profile to the existing user is safer than changing the user
  setting or faking/resetting migrations. No such fallback was silently applied.
- New `accounts/0001_initial` depends on `auth/0012_alter_user_first_name_max_length`
  and `students/0002_external_student_id_normalization`. User is deliberately in
  the initial migration for Django's swappable-user dependency rules.
- The existing permission test that allowed an unlinked mock user was updated to
  assert denial; all other existing tests and development OTP utilities remain.

## Exact identity contract for Developer 1

```python
from apps.accounts.identity import authorized_student_id

student_uuid = authorized_student_id(request.user)
```

Returns the **Student UUID**, never the account UUID or external student ID.
Raises DRF PermissionDenied for anonymous, inactive, staff, superuser, unlinked,
inactive-student, non-BTU, or mismatched-email identities. Missing status
configuration raises ImproperlyConfigured (fail closed). It re-reads the DB,
so a stale user object does not bypass account/student deactivation.

For own Student queries:

```python
Student.objects.filter(pk=authorized_student_id(request.user))
```

For credentials/passports with a canonical Student foreign key, scope the queryset
using that UUID before lookup. Never infer ownership from URL/body identifiers.
Do not compare a Student UUID with request.user.pk. `OwnStudentProfile` can check
Student objects; it is intentionally NOT a generic permission for other models.
Object permissions do not filter list endpoints: queryset scoping is mandatory.
`IsAdmin` requires active staff privileges and excludes Student-linked identities.

`provision_student_account(email)` is an INTERNAL service. It looks up a trusted,
active Student by normalized BTU email, creates an account with an unusable
password, or returns the same linked account. It refuses inactive accounts,
existing unlinked accounts, reassignment, and mismatched links. It accepts no
Student ID and must never be exposed directly as a registration endpoint. The
OTP flow calls it only after proving control of the registered mailbox.

Leave `students/permissions.py:StudentProfileAccessPending` denying access until
Developer 1 integrates and tests scoped Student queries and object checks.

## Shared changes to review with Developer 1 (not applied)

1. Add `django.contrib.contenttypes`, `django.contrib.auth`,
   `django.contrib.sessions`, and `apps.accounts` to INSTALLED_APPS.
2. Set `AUTH_USER_MODEL = 'accounts.User'` BEFORE the first auth migration;
   first confirm existing shared migration history as described above.
3. Enable SessionMiddleware before AuthenticationMiddleware; keep CsrfViewMiddleware.
4. Configure ONLY these login backends:
   - `apps.accounts.authentication.StudentOTPBackend` (session loading; no passwords)
   - `apps.accounts.authentication.AdminPasswordBackend` (active, unlinked staff only)
5. Configure DRF `DEFAULT_AUTHENTICATION_CLASSES` with
   `apps.accounts.authentication.AccountSessionAuthentication` and default
   `IsAuthenticated`; deliberately public verification views must opt out and
   expose only approved public data. Preserve other required DRF settings.
6. Add `path('api/accounts/', include('apps.accounts.urls'))` to config/urls.py.
7. Supply private SECRET_KEY and an independent random ACCOUNTS_OTP_HMAC_KEY
   (at least 32 characters) through secure environment configuration; no defaults.
   Specify ACCOUNTS_ACTIVE_STUDENT_STATUSES as a nonempty list of agreed exact
   Student status strings. The test value `ACTIVE` is not a production assumption.
8. Configure `EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'`,
   EMAIL_HOST, EMAIL_PORT, DEFAULT_FROM_EMAIL, TLS or SSL, EMAIL_TIMEOUT, and any
   required credentials through secure configuration. The service rejects console
   delivery. Email failure or zero deliveries leaves the code consumed; the public
   response stays generic. Add sanitized operational metrics before deployment.
9. Require HTTPS; configure secure session/CSRF cookies, HttpOnly session cookies,
   SameSite policy, trusted origins/allowed hosts, DEBUG=False, DB-backed sessions,
   a short session lifetime (e.g. 30 minutes), and browser-close expiry.
   Never enable ACCOUNTS_ALLOW_UNSAFE_TEST_DB or ACCOUNTS_ALLOW_TEST_EMAIL outside
   isolated tests. Test settings import no .env and never use DATABASE_URL.
10. Review the new migration plan with Developer 1. Apply only with their approval.
    Do not run an unqualified `manage.py migrate` against shared settings.

## Proposed HTTP contract

Paths below are relative to the proposed `/api/accounts/` mount:

- GET `csrf/`: fetch token and CSRF cookie before login.
- POST `otp/request/` with `email`: always 202 and the same generic message for
  valid-shaped eligible, unknown, inactive, malformed, or throttled email input.
- POST `otp/verify/` with `email` and `code`: generic 400 on failed verification;
  200 on success with no user/student identifier in the response.
- POST `logout/`: flush server-side session, return 204.

All POSTs explicitly enforce CSRF, including unauthenticated login requests.
Send the CSRF cookie and X-CSRFToken header; obtain a fresh token after login.
Login rotates the session and CSRF token. OTP consumption, provisioning, and session
persistence share one DB transaction; a session save failure rolls back consumption.
Students cannot use passwords to authenticate with the proposed backends.
Administrators remain on the separate password/admin flow; no admin login UI was added.

## OTP guarantees and limits

- Secrets-generated six-digit codes; keyed SHA-256 hashes tied to normalized email
  and a fresh random nonce, not plaintext storage. Five-minute expiry, five attempts,
  single-use consumption under PostgreSQL row locks.
- Per-email 60-second resend cooldown and five requests/hour. Per-IP request limit
  30/hour and verification limit 60/hour use database-backed counters; malformed
  verification codes consume the attempt budget. Resend replaces the old challenge.
- Rate buckets also exist for unknown addresses. REMOTE_ADDR is used directly:
  no spoofable X-Forwarded-For trust. Behind a proxy, configure trustworthy client
  address handling and gateway limits; otherwise all clients may share a bucket.
- Email delivery is synchronous inside the transaction. Generic responses reduce
  enumeration through content/status, but SMTP latency can reveal registration.
  Queue delivery with safe code handling before claiming timing-enumeration resistance
  or production readiness. Do not store/log raw codes in an unprotected task queue.
- Add gateway body-size/rate limits, monitoring, and a retention/cleanup policy for
  expired challenge and rate buckets. Targeted request floods can exhaust a student's
  login budget; staff recovery procedures and operational controls remain necessary.
- Session loading rechecks Student status/email/account activity on later requests;
  it does not pretend to invalidate an already executing request retroactively.
- No public verification behavior was changed. Existing mock verification remains
  a separate feature and is not proof of official issuance.

## Validation

Python 3.13.5; Django 6.1.2; DRF 3.18.3. Disposable PostgreSQL 17 on loopback port
55432, synthetic data only. A local role matching the OS user and empty
`passport_auth_tests` database are required for the PostgreSQL test settings.
Django creates/destroys `test_passport_auth_tests`. Settings ignore DATABASE_URL.

```sh
cd /workspace/AI-Skills-Digital-Passport/backend
../.venv-auth/bin/python manage.py test apps.accounts apps.students apps.skills apps.integrations apps.verification --settings=apps.accounts.postgres_test_settings
../.venv-auth/bin/python manage.py makemigrations --check --dry-run --settings=apps.accounts.postgres_test_settings
```

SQLite convenience checks (row-lock tests skip; not concurrency validation):

```sh
../.venv-auth/bin/python manage.py test apps.accounts --settings=apps.accounts.test_settings
```

The initial broad SQLite run exposed two pre-existing raw-UUID SQL incompatibilities
in Student/Skill tests; these pass on PostgreSQL. No business logic was changed to
work around those SQLite failures. The committed test settings need no shared credentials.

Final results: 206 tests passed on PostgreSQL with no skips, including simultaneous
successful-code consumers, eight simultaneous wrong-code consumers, and concurrent
first requests. The accounts-only SQLite run passed 48 tests with three concurrency
tests skipped (51 discovered). Migration drift check and `git diff --check` passed.
