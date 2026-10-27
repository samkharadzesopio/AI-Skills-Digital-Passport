# Final frontend/backend integration handoff

Date: 2026-10-27. Frontend branch: `feature/frontend-backend-final-integration`, based on published `fa306748a351a531f97b7a680a1fb77c3376b44e` in a separate worktree. Original checkout, index and local files are preserved. No backend or blockchain implementation is modified, no merge is performed and no push is authorized by this task.

## Backend evidence and limits

Fetched target: `origin/integration`, `bec0d8323ff98cb9e4e83c51f607d23d1e9ab46a`. Inspected authentication views, API serializers, integration URLs/views, verification serializers, proof policy, migrations, local settings and `ops/BACKEND_API_HANDOFF.md` / `ops/BACKEND_CONTRACT_EXAMPLES.json`. Earlier frontend audit documents are historical; this handoff supersedes their provisional proof-mapping limitations.

Important discrepancy: the profile/preview/confirm APIs are **not in this integration commit**. They exist on `origin/feature/flexible-spreadsheet-integration`, which is not an ancestor of integration. Its actual views, preview service and model constraints were inspected read-only to prepare the frontend adapter. This frontend does not merge that branch or claim those endpoints exist in the current target.

## Implemented contracts

- Existing session-cookie authentication routes and exact OTP/admin payloads are retained: `accounts/csrf/`, `otp/request/`, `otp/verify/`, `login/`, `me/`, `logout/`. Existing CSRF bootstrap/rotation, expiry/error handling, ownership and role guards remain. Recognized frontend capabilities survive added backend names; unknown grants cannot authorize UI actions. Legal-identity and direct passport-revocation action screens are not added.
- Existing student dashboard/profile, skills, achievements, credentials, backend-selected current passport, history and exact-version PDF routes remain. No guessed identity or latest-history selection is used. Root `NOT_ISSUED` has an empty state. An active `UNVERIFIABLE` record may prepare its PDF to avoid blocking anchoring, but cannot acquire a current-valid sharing state.
- A modern current-valid passport requires root `BLOCKCHAIN_VERIFIED`, active lifecycle, issued version, positive backend proof verdict, issuer/signer approval and matching passport/version public references. Historical, inactive and unknown records never become current. PDF `ISSUED` remains a file status, not proof success.
- Existing admin statistics, students, credentials, reasoned credential revocation, idempotent issuance and cursor-paginated import/sync history remain. History now includes validation row codes and awarded counts. Classroom remains a simulated, read-only dry-run preview.
- Public passport/reference/PDF verification maps `VALID`, `OUTDATED`, `NOT_FOUND`, `NOT_ISSUED`, `REVOKED`, `REPLACED`, `EXPIRED`, `INVALID`, `PENDING_BLOCKCHAIN` and `UNVERIFIABLE`. Nested failed/pending/unavailable/not-configured evidence remains unverified. A proof-success label requires the documented positive flags, exact proof source, active registry/on-chain states, supported chain/environment pair, transaction hash and confirmations. Reference requests additionally bind the proof reference to the submitted reference. No chain success is inferred from a registry-only result or transaction status alone. Public result state retains only allowlisted display fields, not raw proof data.
- Local import form state remounts on session-context changes, alongside existing query-cache isolation. Private preview data is never persisted in browser storage.

## Reviewed spreadsheet workflow

The adapter consumes only inspected contracts:

1. `GET integrations/import/profiles/?page=N`: bounded, server-authorized source/profile selection; no arbitrary Sheet URL or client-selected Google source ID.
2. `POST integrations/import/excel/preview/`: multipart `profile_id` and bounded `.xlsx` `file`; or `POST integrations/import/google-sheets/preview/`: JSON `profile_id` only.
3. Render returned preview state/expiry, eligible/duplicate/invalid/review counts and row messages/codes. Profile, source and file changes discard the review. The UI does not turn pending/rejected institutional decisions into approved completions.
4. Require an explicit review checkbox, eligible records and an unexpired preview before `POST integrations/import/previews/<id>/confirm/` with the exact reviewed `snapshot_sha256` and `confirm: true`.
5. Render persisted result counts and errors, invalidate private product/history caches, and allow `GET integrations/import/previews/<id>/` to inspect an uncertain outcome. No automatic write retry or locally fabricated import success.

At the current target commit, profile discovery returns a missing-route error and import controls remain disabled. **There is no fallback to the legacy immediate-issuance endpoints.** Completing this workflow requires the backend owner to integrate/deploy the reviewed spreadsheet backend, its migrations and authorized profiles/sources. Google service-account access and approved live Sheet availability remain external dependencies.

## Validation performed

- Production build including TypeScript, Oxlint and all eleven existing non-browser checks passed. Existing architecture, auth/session/CSRF, permission, Demo Mode, template/PDF asset hashes, public transport and lifecycle regressions remain intact.
- Extended `check:product` exercises unavailable-profile behavior without legacy import calls, server-configured Sheets preview, explicit digest-bound confirmation, completed-state guards, Excel multipart preview and source-change review invalidation using synthetic Axios responses and jsdom.
- `check:final-integration` replays selected public responses recorded in the backend team's synthetic acceptance artifact, with negative issuer/signer/type/chain/transaction tests and private reference-binding checks. These recorded responses are fixtures, not live-service calls made during this task.
- `check:passport-layout` passed at 1920x1080, 1366x768, 1024x768, 768x1024, 390x844 and 375x667, including all 33 variable-content pages, using isolated Chromium with API traffic blocked. Official artwork/navigation/scaling code is preserved.
- Existing approximately 770 kB main JavaScript chunk warning remains. This is not a failed build.
- Local `GET http://127.0.0.1:8000/api/accounts/csrf/` could not connect. No Django/PostgreSQL end-to-end test or actual blockchain confirmation was performed. No database credential, data or migration state was changed.

## Final integration testing steps

1. Backend owner prepares a separate backend checkout at the verified target (and explicitly integrates the missing spreadsheet feature through the team's process). Preserve existing worktrees. Install that checkout's requirements into its own virtual environment.
2. Obtain PostgreSQL credentials through a masked local prompt, inspect `btu_passport_local` read-only and report its migration state. Obtain approval before applying migrations or changing data/configuration. Do not reset or recreate it. New target migrations include passport lifecycle/integrity and blockchain proof tables; spreadsheet migrations are absent from `bec0d83` and must come from the reviewed feature.
3. Configure ignored backend environment values under the documented local policy: `BTU_LOCAL_DEVELOPMENT=1`, `DJANGO_DEBUG=true`, loopback PostgreSQL database `btu_passport_local`, explicit active student statuses, approved issuers/import sources and private PDF storage. Keep secrets outside Git. Use `config.local_dev_settings`; it preserves authentication/authorization and uses a private local mailbox.
4. From that configured backend virtual environment, inspect before mutation:

   ```powershell
   python manage.py check --settings=config.local_dev_settings
   python manage.py showmigrations --settings=config.local_dev_settings
   python manage.py migrate --plan --settings=config.local_dev_settings
   ```

   Apply only reviewed migrations after explicit database approval. Then run `python manage.py runserver 127.0.0.1:8000 --settings=config.local_dev_settings`. Do not start the older backend copied into this frontend worktree as though it were the target.
5. From this worktree's `frontend` directory:

   ```powershell
   npm.cmd ci
   $env:VITE_ENABLE_DEMO='false'
   $env:VITE_PUBLIC_VERIFICATION_ENABLED='true'
   $env:VITE_PUBLIC_VERIFICATION_SOURCES='POSTGRESQL_PASSPORT_REGISTRY,POSTGRESQL_DOCUMENT_REGISTRY'
   npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
   ```

   Use the existing same-origin `/api/` proxy to port 8000. Browser email/admin passwords and OTPs must be entered interactively, not copied into source, fixtures or chat. Keep one host name throughout cookie/session testing.
6. Use authorized synthetic institutional student/admin records. Test admin login/restoration, approved-source preview (including rejected/pending/duplicate/error rows), explicit confirmation, persisted credential/passport changes, student OTP/restoration and no-passport state, exact PDF preparation/download, anonymous reference/PDF verification, revocation/replacement/history, expired/reused OTPs, cross-student denial and capability/CSRF denial. Recheck source/profile changes, expired previews and interrupted confirmations before retrying.
7. Configure an actual approved Anvil/Amoy deployment and backend workers according to `blockchain/API_CONTRACT.md` and its stabilization handoff. Verify actual transaction confirmation and backend proof binding before accepting the positive badge. Repeat with failed/unavailable/unconfigured provider states. A recorded confirmed fixture does not satisfy this acceptance step.

The deliverable is a frontend adapter ready for joint testing, with explicit unsupported-backend states. The full live administrator-import-student-PDF-public-verification demonstration remains blocked on the above environment and missing spreadsheet backend integration.
