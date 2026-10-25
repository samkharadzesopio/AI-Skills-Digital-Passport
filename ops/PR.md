# Joint backend integration candidate

Candidate branch: `integration-candidate/dev1-dev2`, based on `origin/integration`
at `c64d4a2`. It integrates Developer 1's Credential-to-Passport lifecycle work
(`43782c1`) and Developer 2's Classroom/import, verification, and security work
(`385896b`). It retains the existing app and service ownership boundaries.

## Included

- Durable Credential issuance/revocation to Passport refresh records, bounded workers,
  retry/reconciliation and expiration refresh scanning.
- Durable Classroom completion and spreadsheet import inboxes, idempotency,
  concurrency handling and retry recovery.
- PostgreSQL credential/PDF verification, explicit issuer trust checks, bounded
  public uploads and persistent rate limiting.
- Queued authentication mail and protected-action audit records.
- Fixed `BTU-UNIVERSITY` issuer binding. HTTP clients cannot provide an issuer;
  public verification requires an allowlisted reference and a trusted database row.
- A combined end-to-end regression covering a synthetic completion through verified
  achievements, credential, Passport snapshot, stored PDF hash and public verification.

## Migrations and validation

Additive migrations in the candidate are accounts/0006,
credentials/0005, integrations/0001 and 0002, and passports/0005. The combined
graph applied from zero on disposable loopback PostgreSQL 18.6. Safe reverse/reapply
cycles passed for Credential/Passport, Integrations and Accounts migrations. A
synthetic pre-outbox Credential fixture upgraded and backfilled one pending Passport
refresh. No migration was applied to shared Neon.

Final regression run: 364 passed, 0 failed, 0 errored; 2 legacy reference-schema
comparisons were excluded by the pre-existing test runner. Django system checks and
`makemigrations --check --dry-run` passed. The 5,000-student synthetic test completed
in 1.121 seconds (test body), verified one query for a Passport lookup, and asserted
an index scan. This is a local fixture result, not a throughput or capacity claim.

## Remaining rollout gates

- The Classroom service still reads server-owned simulated records; no real BTU
  Classroom API connector or upstream event contract is available.
- Live SMTP and Google Sheets credentials were not supplied or tested. The
  institution must approve statuses, mappings and evidence-source policies.
- `run_backend_workers` is not deployed or supervised in this candidate. Configure
  it on the target platform and monitor retries before live synchronization.
- PDF verification proves registered bytes and latest version, not current validity
  of every credential represented in that historical PDF. Use credential
  verification for revocation and expiry status.
- No HTTP load test or production connection-pool measurement was performed.

Use an approved staging/Neon branch for migration review and operational smoke tests.
No production migration, deployment, commit to `main`, or live source synchronization
occurred during local validation.
