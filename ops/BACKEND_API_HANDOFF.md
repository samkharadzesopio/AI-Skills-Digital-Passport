# Combined backend API handoff

The HTTP paths and example bodies in [BACKEND_CONTRACT_EXAMPLES.json](BACKEND_CONTRACT_EXAMPLES.json)
come from the real loopback Django/Anvil acceptance driver. All people, accounts,
records, registry addresses and transactions are synthetic. Requests use session
cookies and CSRF; examples deliberately contain no passwords, OTPs, cookies,
CSRF tokens or signing keys. Timings/RPC counts are local observations, not a
deployment SLA. The earlier blockchain/API_EXAMPLES.json remains illustrative.

## Existing contracts retained

| Purpose | Actual endpoint and important fields |
| --- | --- |
| CSRF bootstrap | GET `/api/accounts/csrf/`; `csrfToken`, session CSRF cookie |
| Student login | POST `/api/accounts/otp/request/` with `email`; POST `/api/accounts/otp/verify/` with `email`, `code` |
| Admin login/context | POST `/api/accounts/login/` with `email`, `password`; GET `/api/accounts/me/`; `role`, `email_verified`, `student_association`, `capabilities` |
| Logout | POST `/api/accounts/logout/`; invalidates session; unsafe requests require CSRF |
| Student profile/summary | GET `/api/student/dashboard/`; `profile`, recognized skill/achievement/credential counts, recent records, `passport` |
| Own credentials | GET `/api/student/credentials/` and `/api/student/credentials/<credential UUID>/`; status and current `validity_status` are separate |
| Current identity | GET `/api/student/passport/`; identity `id`, `public_reference`, `status`, `lifecycle_status`, `first_issued_at`, `latest_version`, `blockchain`; no identity returns `{"passport": null}` |
| Current identity's history | GET `/api/student/passport/versions/` and `/api/student/passport/versions/<version UUID>/` |
| Official PDF | POST `/api/student/passport/pdf/` with `{}`; GET `/api/student/passport/pdf/status/`; GET `/api/student/passport/pdf/download/`; corresponding `/versions/<version UUID>/pdf/...` routes retain exact-version selection |
| Admin records | GET `/api/admin/students/`, `/api/admin/passports/?student_id=<Student UUID>`, `/api/admin/passports/<Passport UUID>/versions/` |
| Historical Admin PDF | GET `/api/admin/passports/<Passport UUID>/pdf/download/?version_id=<version UUID>`; selecting no version uses that identity's latest version; requires explicit read permission and is audited |
| Approved Excel import | POST multipart `/api/integrations/import/excel/`; `file` is a bounded xlsx completion workbook; explicit `import_completions` and server-authorized source required |
| Google Sheets | POST `/api/integrations/import/google-sheets/`; uses server-configured sheet and service account, never a client-selected source |
| Classroom | `/api/integrations/classroom/completions/`, `/classroom/sync/`, `/classroom/events/`; simulated BTU adapter, explicit `sync_classroom` |
| Skills Gap Analyzer | GET `/api/integrations/course-recommendations/`; own Student only; existing service, verified evidence and bounded filters retained |
| Public verification | GET `/api/verification/passport/<public Passport reference>/`, `/passport-version/<public version reference>/`; POST multipart `/api/verification/document/` with `file` |
| Independent proof view | GET `/api/verification/blockchain/document/<public document reference>/`; read-only, minimal proof facts |

The older Student profile route is also retained at
`/api/students/students/<student identifier>/`. Use the dashboard's authoritative
profile for the existing frontend flow; do not confuse external university IDs,
internal Student UUIDs, permanent Passport IDs and version IDs.

## Lifecycle actions

POST `/api/admin/students/<Student UUID>/legal-name-change/` requires
`manage_legal_identity` and these exact fields:

```json
{
  "expected_passport_reference": "<current public Passport UUID>",
  "first_name": "<approved new first name>",
  "last_name": "<approved new last name>",
  "idempotency_key": "<stable reviewed request key>",
  "evidence_source": "<server-allowlisted source>",
  "evidence_reference": "<private approval reference>",
  "reason": "<private institutional reason>"
}
```

The response contains `event_id` and the replacement `passport`. Matching replay
returns the same event; conflicting replay or changed expected identity returns
409. Approval preserves credential ownership and old frozen documents. The old
identity becomes REPLACED immediately; new chain validity depends on confirmed
old-identity cancellation plus the replacement's exact document commitment.
Read private audit history at GET
`/api/admin/students/<Student UUID>/passport-lifecycle/` with the registrar grant.

POST `/api/admin/passports/<Passport UUID>/revoke/` requires
`manage_passport_lifecycle`, `idempotency_key`, and `reason`. Its response is
`event_id` plus `status: REVOKED`. Existing credential revocation remains POST
`/api/admin/credentials/<credential UUID>/revoke/` with `reason` and the separate
`revoke_credentials` grant. New capabilities appear in session context only when
explicitly granted. Neither ADMIN role nor an unrelated capability grants them.

## State interpretation

Public current success is `VALID`; private current success is
`BLOCKCHAIN_VERIFIED`. A positive current badge also requires
`blockchain.blockchain_verified === true`, approved institutional issuer and
authorized signer. `lifecycle_status` describes the permanent identity; it is
separate from the live proof verdict in `status`.

Genuine work in progress is `PENDING_BLOCKCHAIN`. Unconfigured, failed or
unavailable proof maps to root `UNVERIFIABLE`, with the precise nested proof
state (`NOT_CONFIGURED`, `FAILED`, `UNAVAILABLE` or `UNVERIFIABLE`). These never
produce a positive badge. `REPLACED`, `REVOKED`, `EXPIRED`, and `INVALID` take
precedence. `OUTDATED` describes a historical version. `authentic` and
`historical_blockchain_authentic` describe retained evidence, not current
institutional certification. An issued PDF's `status: ISSUED` describes the file,
not confirmation of a blockchain transaction.

A recognized public Passport reference without an issued version returns
`NOT_ISSUED` with `authentic: false`; unknown/invalid references return
`NOT_FOUND`. Neither response exposes Student data or creates a version.
Unknown document bytes never inherit the proof of a similarly named PDF.

## Frontend work still required

No React implementation was modified. The existing frontend needs these precise
changes during final website integration:

1. `frontend/src/verification/contracts.ts` and its adapters currently allow only
   the older public statuses. Add `PENDING_BLOCKCHAIN`, `REPLACED`, and
   `NOT_ISSUED` handling and retain the nested proof facts. Pending must remain
   visibly pending; unavailable/unconfigured/failed must remain unverified.
2. `frontend/src/student/contracts.ts` parsers currently discard `blockchain`,
   `lifecycle_status` and `first_issued_at`, including PDF proof metadata.
   Preserve and render these fields without deriving chain success from ISSUED.
   Update `student/adapter.ts` and Passport/PDF views accordingly.
3. `frontend/src/auth/contracts.ts` explicitly allowlists the original six
   capabilities. Add the two lifecycle capabilities before exposing permissioned
   registrar/revocation controls; keep capability-specific authorization.
4. `frontend/src/admin/live/PassportPage.tsx` defaults to `rows[0]` for a Student.
   Select `lifecycle_status === 'ACTIVE'` for the default current identity and
   make historical REPLACED/REVOKED identity selection explicit. Preserve Admin
   historical versions and audited PDF downloads.
5. Refetch current identity/version/proof after lifecycle actions, and clear old
   private caches on logout/account/identity changes. Student version and PDF
   routes exclude cancelled identities; authorized Admin history remains usable.
6. Test the updated UI with chain enforcement enabled. Existing Vite/DOM-driver
   suites intentionally use registry-only legacy test settings; their passing
   result does not establish visual-browser or blockchain-aware UI acceptance.

Google service-account/live-sheet acceptance and a real BTU Classroom API remain
external dependencies. The supported spreadsheet pathway consumes approved
course-completion columns, not an arbitrary university workbook layout. Source
mapping must preserve the university's confirmation decision: pending/rejected
records must never be submitted as approved completions.
