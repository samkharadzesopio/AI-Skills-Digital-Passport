# Google student authentication

GIS popup/JavaScript callback uses the existing Django cookie session. Student
OTP and administrator password authentication remain available. Google never
registers an official Student, changes awards or grants admin capabilities.

## Local setup

Use an OAuth **Web application** client. Authorized JavaScript origin for this
isolated review: `http://127.0.0.1:5188` (no path/trailing slash). No Client Secret
and no authorized redirect URI are used. Production needs its actual HTTPS
frontend origin, same-origin `/api/` routing and appropriate Google consent/
Workspace audience configuration. No deployment origin is invented here.

Set the **same public Client ID** privately in these ignored files:

```dotenv
# frontend/.env.local
VITE_GOOGLE_CLIENT_ID=<your Web Client ID>
```

```dotenv
# backend/.env
GOOGLE_OAUTH_CLIENT_ID=<the same Web Client ID>
```

With the ID saved in a private one-line file, run
`python -B ops/configure_google_auth.py --client-id-file ABSOLUTE_PRIVATE_FILE`.
It updates only those two settings, preserves other settings/comments and refuses
duplicates/concurrent edits without printing values. Never supply credentials JSON
or a secret. Sheets' `GOOGLE_SERVICE_ACCOUNT_FILE` is unrelated and unchanged.
Restart Vite/Django after configuration. Missing configuration fails closed.

For an owned synthetic-record website, set short unique TEMP/TMP directories,
`PASSPORT_PG_BIN`, `PASSPORT_ANVIL_BIN` and run:

```text
python -B ops/run_isolated_tests.py --google-auth-review --review-stop-file ABSOLUTE_NEW_FILE.stop
```

This keeps fresh local PostgreSQL, Anvil, Django and Live Vite running on strict
frontend port 5188 (`BTU_GOOGLE_AUTH_PORT` can explicitly override it). It refuses
an occupied port. Only Client ID settings are read from the local env files;
production DB/Sheets configuration is never loaded. Runtime URLs and the private
synthetic administrator/OTP mailbox file path are in `review-ready.json` beside
the stop file. Create that stop file for owned cleanup. Existing services remain
untouched. This review session is not production hosting or reboot persistence.

The initial Continue with Google control prepares a fresh server nonce and loads
GIS only after explicit interaction. GIS then renders its official Continue with
Google button, which opens the popup. No One Tap or automatic sign-in is enabled.
Keep Google tokens out of storage, URLs, logs and recordings. In production, allow
Google's GIS endpoints in any CSP and use popup-compatible COOP on the login/link
document (for example `same-origin-allow-popups` when FedCM is unavailable), without
weakening API session/CSRF policies. See Google's current
[GIS setup](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid).

## Linking and endpoints

1. An institution must already have provisioned an eligible canonical Student.
2. Student signs in with the existing email OTP. Only that successful flow records
   a five-minute, user-bound proof in the existing server-side session.
3. Student opens **Google sign-in settings** from the Student workspace and
   explicitly links the same institutional Workspace identity.
4. Later Google logins resolve the unique immutable `sub` binding and recheck
   active account, institutional status, email consistency and least privilege.
   A Google session alone cannot authorize initial linking. Subject/email changes,
   conflicting links and recovery require a separate reviewed institutional flow;
   there is no automatic reassignment/unlinking API.

- POST `/api/accounts/google/challenge/` with `{"intent":"login"}` or `"link"`.
  Returns `challenge_id`, `nonce`, `expires_in` (300 seconds).
- POST `/api/accounts/google/authenticate/` with `challenge_id`, `credential`.
  Returns the existing bounded account summary under `account`, plus `linked`.
  The browser then restores `/api/accounts/me/` as it does for OTP.

Both endpoints enforce Django CSRF, durable rate budgets and sanitized security
audit. Nonces are HMAC-stored, session/intent/user/audience-bound and atomically
consumed once, including invalid-token/provider-failure attempts. Concurrent replay
gets one verification attempt. Signature/issuer/audience/authorized-party/expiry,
verified email, exact BTU email and `hd=btu.edu.ge` are checked server-side via
`google-auth` plus explicit policy checks. Missing/wrong `hd` is rejected; never
weaken this rule without owner approval. Google public certificates use a fixed
HTTPS endpoint, bounded fetch and Cache-Control-aware cache; no user Google API
access/refresh tokens or Sheets scopes are requested.

Migration `accounts.0008_google_identity` adds `GoogleIdentity` (unique subject,
one-to-one User, immutable binding trigger) and `GoogleLoginChallenge` (one-use
nonce metadata with expiry index). Existing Student/User/award/Passport rows are
not backfilled or rewritten. Operational retention for expired nonce/audit rows
should follow the institution's existing security-data retention policy.

## Validation and delivery boundaries

Run `python -B ops/run_isolated_tests.py --google-auth --google-auth-browser` with
the repository's documented PostgreSQL/Anvil and Chrome tool paths. Automated
Google identity uses synthetic RSA signatures, keys and GIS responses; no real
Google requests are authorized by those flags. Actual React/Django/PG sessions,
OTP, CSRF, endpoints, linking, role checks, replay and logout are exercised.

Final targeted backend suite: **107 passed**, including migration preservation
and concurrent nonce consumption; local env preservation helper: **4 passed**.
Actual Chrome acceptance: **5 groups / 46 page API responses**, Google GIS/keys
synthetic; no Django API responses intercepted. Frontend build/lint and auth,
architecture, Demo isolation and Student integration regressions passed. Initial
development runs exposed a PostgreSQL outer-join lock issue and two test-helper
mistakes; corrected and affected tests passed. No full application audit rerun.

The owner later authorized normal integration merge/push after quality gates.
Remote state must be rechecked before delivery; no force push or `main` change.
Client IDs, env files, mailbox contents, test private keys and screenshots stay
outside Git. Real Google sign-in remains **UNVERIFIED**, requiring separate
owner approval and confirmed intended BTU test accounts/configuration. No real
student data or public deployment is authorized by this local validation.
