## Backend automation, verification and security integration

Connects trusted simulated Classroom completions and explicitly authorized spreadsheet
sources to existing achievement/credential services, with a durable inbox, stable
idempotency, retries and recovery of achievements missing credential issuance.
Replaces production mock verification with PostgreSQL credentials and the existing
PassportDocument repository. Adds bounded public uploads and persistent throttling.

Security work queues login/recovery mail outside HTTP/SMTP timing paths, preserves
single-use OTP/session checks, and records sanitized protected-action audit outcomes.
Shared settings now bind approved issuer/source policies; portable preflight and
worker commands make the remaining staging setup reviewable.

### Migration review

New additive migrations: accounts/0006_deferredmail_securityaudit,
integrations/0001_initial, integrations/0002_importrun_and_more. Existing auth/domain
migrations are unchanged. No shared Neon migrations were applied. Developer 1 must
review existing schema/history and approve the plan before applying it.

### Validation

Final run: 342 tests passed on isolated PostgreSQL (344 discovered, two explicitly excluded). Run ops/test_backend.sh to reproduce. The existing runner explicitly
excludes two legacy reference-schema comparison tests; concurrency assertions run.
The migration graph was applied successfully to a fresh disposable local database;
re-running the plan reported no pending operations. The Gunicorn local smoke returned database-backed NOT_FOUND and private-profile HTTP 403; an empty worker cycle completed successfully.
No live SMTP/Google or production performance results are claimed.

### Remaining rollout gates

- Developer 1 approves/provisions issuer, source/status policy and migration plan.
- Configure actual deployment host, credentials, gateway limits and workers.
- Developer 1 completes reliable credential lifecycle-to-Passport updates, ordering
  and expiry handling. No duplicate publishing logic is introduced here.
- Confirm PDF integrity/latest semantics separately from credential validity.
- Run the live staging acceptance checklist in ops/README.md.

Do not merge before joint review and staging acceptance. No automatic deployment
or merge was performed.
