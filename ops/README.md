# Combined backend integration, 27 October 2026

The lifecycle/blockchain integration uses the existing disposable runner with all
nine backend applications. Run `python -B ops/run_isolated_tests.py --full` with
the pinned Python requirements, local PostgreSQL binaries, existing frontend
test dependencies and pinned `blockchain` npm dependencies installed. The runner
creates its own fresh cluster; no existing development database is adopted.

Current handoff documents:

- [Backend API contracts and remaining frontend work](BACKEND_API_HANDOFF.md)
- [Captured synthetic HTTP/Anvil examples](BACKEND_CONTRACT_EXAMPLES.json)
- [Persistent-data migration and worker runbook](BACKEND_MIGRATION_RUNBOOK.md)

Public Polygon deployment, persistent database migration and live institutional
service acceptance remain separate operator steps. No React implementation is
changed by the backend integration.

# Historical review and staging rollout

The following notes describe the earlier pre-blockchain candidate. Use the
current documents above for lifecycle schema, testing and worker sequencing.

This is a locally validated integration candidate, not evidence of production
deployment. Do not apply shared Neon migrations without institutional approval or
deploy the simulated Classroom completions as live evidence.

## Current evidence and blockers

The candidate is based on integration c64d4a2 and combines Developer 1's
Credential-to-Passport lifecycle automation with Developer 2's Classroom/import,
verification, and security work. The branches were tested together on disposable
local PostgreSQL 18.6; no shared Neon migration or production deployment occurred.

No deployment platform/project/URL or live SMTP/Google/Classroom/Neon settings were
supplied. No production secrets were read, copied, invented or committed. The fixed
internal issuer is `BTU-UNIVERSITY`; an authorized administrator must provision its
trusted record. Student status and evidence-source policies still require
institutional approval. See DEVELOPER1_HANDOFF.md for remaining owner dependencies.

## Verify locally first

Python 3.13.13, Django 6.1.2, and disposable PostgreSQL 18.6 on 127.0.0.1:55435.
The combined test settings ignore `.env` and `DATABASE_URL` and create/destroy a
uniquely named test database. Set `FOUNDATION_TEST_PG_HOST=127.0.0.1`,
`FOUNDATION_TEST_PG_PORT=55435`, `FOUNDATION_TEST_PG_PASSWORD` to a local-only test
value, and `AUTH_TEST_PG_PORT=55435` before running the suite.

```
PASSPORT_PYTHON=/absolute/path/to/venv/bin/python ./ops/test_backend.sh
```

The existing runner explicitly excludes two reference-schema comparisons. It does
not skip the concurrency tests. No statement of 5,000-student throughput is made.

## Approve and prepare staging

1. Review diff, test results and the exact migration plan with Developer 1.
   Review existing django_migrations and any legacy auth/schema.sql tables read-only.
2. Take/verify a database backup or Neon branch. Use staging first. Run only the
   approved migration plan after their approval; do not fake/reset migrations.
3. Install pinned requirements. Supply secrets through the host's secure store.
   Use backend/.env.example only as a list of names, not as production secret values.
4. Keep `BTU_CLASSROOM_ISSUER_REFERENCE` fixed at `BTU-UNIVERSITY`. Configure the
   trusted issuer allowlist and institutional values in config/settings.py:
   VERIFICATION_TRUSTED_ISSUER_REFERENCES,
   BTU_AUTHORIZED_COMPLETION_SOURCES, BTU_GOOGLE_SHEET_ID and
   GOOGLE_SERVICE_ACCOUNT_FILE. Empty issuer/source policies deliberately fail closed.
5. Run `python manage.py check --deploy` and `python manage.py deployment_preflight`.
   Preflight is read-only: it checks pending migrations, trusted BTU issuer presence,
   required security policy, source settings and credential-file presence. It never
   migrates, creates issuers, sends email or verifies live credential contents.

## Processes and gateway

Run from repository root using the deployment's configured private environment:

```
gunicorn --config "$PWD/ops/gunicorn.conf.py" --chdir backend config.wsgi:application
python backend/manage.py run_backend_workers
```

The web configuration binds loopback by default. For a container platform that
requires a public container interface, use an explicit `--bind 0.0.0.0:$PORT`
behind the host's HTTPS ingress. No user-facing loopback preview link is supported.
The worker drains at most 100 mail jobs per cycle, polls event/import/Passport
refresh processing and bounded expiration scans once per minute, and invokes
cleanup/session expiry hourly. Passport batches are capped at 500. It never applies
migrations, provisions issuers, or ingests mock Classroom completions.
Use the host's supervisor to restart workers and send alerts on sanitized failures.
`run_backend_workers --once` is a bounded process smoke check.

Gateway requirements: HTTPS, allowed hosts/origins, request-body limit 6 MiB,
bounded multipart fields, URL/header limits, connection/body read timeouts and
global rate limits. Trust forwarding headers only from that gateway. Defaults use
REMOTE_ADDR and ignore X-Forwarded-For; choose a trusted client-IP strategy before
rollout or users behind a proxy share application rate budgets. Gunicorn header
limits do not replace a total body limit. No gateway was configured without a target.

SMTP needs outbound access to the approved host/port. Google needs read-only service
account access and HTTPS destinations oauth2.googleapis.com/sheets.googleapis.com.
Do not weaken certificate/TLS verification. Do not pass credentials in command lines.

Auth cleanup now retains delivery-control rows for at most a day and audit rows
for 30 days, deleting in bounded batches of 1,000 per hourly cycle. Confirm this
policy with the institution; extend it before rollout if required. High volumes
may need more frequent cleanup/partitioning. Backups and DB access controls remain
necessary; application audit data is not tamper-proof against a database owner.

## Live acceptance checklist (requires actual staging access)

- Registered student requests a code; worker sends it; login succeeds once, then
  logout/deactivation rejects the old session; unrelated Student IDs remain denied.
- Unregistered/inactive addresses receive the same HTTP message and no code.
- Approved simulated or real institutional event yields one credential; replay and
  retry preserve IDs. Never inject arbitrary rows as approved institutional evidence.
- Authorized Excel/Google import records a durable run and handles invalid/duplicate
  rows; unauthorized actors/sources cannot issue credentials.
- The shared worker refreshes the Passport after issuance/revocation, retries after
  interruption, and schedules bounded expiration refreshes without stale latest.
- Generated PDF verifies by bytes; a changed upload is unverifiable, a prior version
  is outdated. PDF authenticity/latest fields remain separate from the aggregate current credential status; revoked/expired contents cannot report overall VALID.
- Public verification works with no account or stale cookies; per-IP rate limits,
  upload limits, no-store headers and response privacy hold behind the actual gateway.

Local synthetic tests do not establish any of these live-service results. Stop on
an unexplained failure; do not deploy or merge merely because a preflight passed.

## Earlier rollout validation (before f8057c5)

The final combined PostgreSQL run passed 364 tests (366 discovered; two existing
legacy schema comparisons excluded). Django system checks and
`makemigrations --check --dry-run` passed. All migrations applied from zero on a
disposable local database; safe reverse/reapply cycles and a synthetic legacy
Credential outbox backfill also passed. The end-to-end synthetic completion through
Passport PDF and public verification passed. The 5,000-student identity test ran in
1.121 seconds, asserted a single Passport retrieval query and an index scan. This is
not a concurrent-user or production-throughput measurement. No HTTP load test,
production-settings deployment check, live SMTP/Google/Classroom access, or shared
Neon migration was performed during this checkpoint.

Current verification validation: 379 tests passed (381 discovered, two legacy comparisons explicitly excluded). See backend/apps/verification/docs/PERFORMANCE.md for current measurements and INTEGRATION_REVIEW.md for status/API compatibility.
