# BTU Workspace portal authentication — 2026-10-29

The owner's final policy allows **any verified BTU Google Workspace account,
including alumni and staff**, to enter a personal portal. No eligibility roster
or enrollment check is required for basic access. The internal STUDENT role is
the least-privilege portal role; it does not certify current enrollment.

## Identity and record ownership

- The existing login artwork, layout, tabs and primary pink styling are retained.
  The Student form has one **Sign in** button, no email/OTP form or second Google
  button. Administrator password login and public verification remain available.
- The button uses browser FedCM active mode with Google's provider configuration.
  A one-use, session-bound nonce is prepared before the user gesture. Signature,
  issuer, audience/authorized party, expiry, verified email, exact BTU email
  domain, `hd=btu.edu.ge`, nonce and stable `sub` are checked server-side.
- A new `sub` creates an independent portal-only account, with an unusable
  password and no academic Student, awards, Passport, PDF or proof. A recycled
  or matching student/administrator email never attaches historical records or
  transfers privileges through the Google login path. Repeat login resolves by
  `sub`, including a legitimate verified BTU email rename.
- Existing protected Google bindings retain their trusted record association.
  New portal principals require an explicitly approved institutional `sub` to
  `external_student_id` mapping before accessing academic records. Until then,
  all private record endpoints deny access and the UI shows a useful empty
  portal. No roster is needed to log in.
- Trusted operators may load a bounded JSON list containing `google_sub` and
  `external_student_id` with `manage.py provision_portal_mapping --file <private
  file> --actor-id <authorized-admin-uuid> --approval-reference <source-reference>`.
  This requires `accounts.manage_student_accounts`, records an audit event,
  rejects ownership conflicts, and creates immutable mappings. An existing
  Google identity must exist first. Never derive this mapping from email alone.
  Approved future awards resolve through the canonical institutional student ID.
- Existing OTP APIs remain available under their existing provisioning rules;
  they are absent from the normal Student login screen. Password/OTP lookups
  exclude portal-only accounts. Legacy account emails remain unique; portal
  principals are uniquely bound by Google subject. Django's `auth.W004` is
  expected for the shared email field; custom backends isolate the namespaces.

## Hosting configuration and remaining external verification

- Same public Web Client ID: frontend `VITE_GOOGLE_CLIENT_ID`, backend
  `GOOGLE_OAUTH_CLIENT_ID`. The isolated checkout's ignored env files were
  configured privately, preserving unrelated variables. No Client Secret or
  OAuth redirect URI is used by this browser-token flow.
- Registered local origin: `http://127.0.0.1:5188`. Register the exact approved
  HTTPS frontend origin in Google Console before hosting; no deployment origin
  has been assumed. Serve `/api/` from the same origin and configure the existing
  Django production secret, HMAC, host, CSRF, secure-cookie and database settings.
  Apply migration `accounts.0009_workspace_portal` through the deployment process.
  No persistent database migration or hosting deployment was performed here.
- FedCM active mode requires a supported current browser and browser/user
  permission. Unsupported browsers fail clearly. This is a browser-mediated
  chooser, not a hidden Google button or a scripted popup.
- **Live Google authentication remains unverified and requires separate approval.**
  Browser acceptance substitutes FedCM identities and signing keys only; the
  React/Django/session/PostgreSQL/Anvil resources and API responses are real and
  disposable. No Google APIs, credentials, real student data or public chain
  were used. Verify actual Google chooser, authorized origin, token claims and
  Workspace policy on the final host before declaring production authentication
  ready. Institutional ownership mappings remain an operator responsibility.

Primary browser integration references:
[FedCM relying-party implementation](https://developer.chrome.com/docs/identity/fedcm/implement/relying-party),
[Google FedCM guidance](https://developers.google.com/identity/gsi/web/guides/fedcm-migration).

## Validation

- 112 account/security tests and four environment-configuration tests passed on
  disposable local PostgreSQL; migration preservation and drift checks passed.
- Frontend production build, lint, authentication and access-boundary checks passed.
- Chrome acceptance: five groups, 45 actual API responses, no API response mocks,
  no page errors; synthetic FedCM/provider keys, no live Google authentication.
- 60 additional API/PDF/issuer regression tests passed. Retained OTP HTTP
  acceptance passed with 68 real requests, current/historical PDF downloads,
  public byte verification, logout, ownership denials and CSRF rejection.
  Its jsdom driver emitted React `act` warnings; native Chrome had no page errors.
  Delivery logs/screenshots are under `student-portal-auth-20261029` outside Git.

Scope: no changes to issued artifacts, awards, synchronization workers, blockchain
verification rules, existing developer worktrees or `main`. Normal integration
delivery is authorized by the owner after these quality gates pass.
