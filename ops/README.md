# Review and staging rollout

This is a reviewable rollout package, not evidence of production deployment.
Never merge automatically. Never apply shared Neon migrations without Developer 1's
approval. Do not deploy institutional sample completions as live evidence.

## Current evidence and blockers

The feature branch includes integration c64d4a2 and all Developer 2 phases. Native
Git operations work, but GitHub API requests returned Forbidden; no PR was created
through the API. PR text is in PR.md. Use the comparison link in the chat to open
it manually, or restore API access to let the assistant create it.

No deployment platform/project/URL or live SMTP/Google/Neon settings were supplied.
No production secrets were read, copied, invented or committed. Issuer approval,
Student status policy and source approval must come from Developer 1/institution.
Credential-to-Passport orchestration remains Developer 1's pending owned contract;
see DEVELOPER1_HANDOFF.md. Do not call it complete merely because credential
issuance or independent PDF generation passed tests.

## Verify locally first

Python 3.13, requirements.txt installed, disposable PostgreSQL on 127.0.0.1:55432,
current OS role and classroom_tests DB. The test settings ignore .env/DATABASE_URL.

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
4. Configure the institutional values now bound in config/settings.py:
   BTU_CLASSROOM_ISSUER_REFERENCE, VERIFICATION_TRUSTED_ISSUER_REFERENCES,
   BTU_AUTHORIZED_COMPLETION_SOURCES, BTU_GOOGLE_SHEET_ID and
   GOOGLE_SERVICE_ACCOUNT_FILE. Empty issuer/source policies deliberately fail closed.
5. Run `python manage.py check --deploy` and `python manage.py deployment_preflight`.
   Preflight is read-only: it checks pending migrations, approved issuer existence,
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
The worker drains at most 100 mail jobs per cycle, polls event retries/import
reconciliation once per minute, and invokes cleanup/session expiry hourly. It never
applies migrations, provisions issuers, or ingests mock Classroom completions.
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
- Developer 1's lifecycle worker refreshes the Passport after issuance/revocation,
  retries after interruption, handles delayed events and expiry without stale latest.
- Generated PDF verifies by bytes; a changed upload is unverifiable, a prior version
  is outdated. PDF integrity/latest status is separate from current credential validity.
- Public verification works with no account or stale cookies; per-IP rate limits,
  upload limits, no-store headers and response privacy hold behind the actual gateway.

Local synthetic tests do not establish any of these live-service results. Stop on
an unexplained failure; do not deploy or merge merely because a preflight passed.

## Final local validation

342 tests passed (344 discovered, two explicitly excluded legacy schema comparisons).
No migration drift; a complete fresh local migration run succeeded and its repeated
plan was empty. Gunicorn 26.2.0 booted with the documented config, returned real
DB-backed NOT_FOUND for an unknown public reference and HTTP 403 for the private
profile route. The isolated worker --once cycle passed with no queued deliveries.
These checks used isolated settings and synthetic data, not live production secrets.

A separate production-settings `check --deploy` using synthetic configuration passed
with W005/W021 warnings: HSTS subdomains and preload were intentionally not enabled
without knowing the domain's policy. They require the domain owner's decision;
turning them on blindly can break unrelated subdomains. Review before live rollout.
