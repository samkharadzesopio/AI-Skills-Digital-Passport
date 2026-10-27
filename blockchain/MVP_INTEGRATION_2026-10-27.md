# Blockchain MVP integration follow-up — 27 October 2026

This is the historical `c87f801` follow-up report. Its public-Amoy requirement
is superseded by the current Anvil-first scope; its recorded results and initial
unexplained HTTP failure remain historical evidence. See
[fresh candidate validation](../ops/BACKEND_ANVIL_STABILIZATION.md).

## Historical readiness: NOT READY for the former complete MVP acceptance

The local backend corrections and normal HTTP acceptance pass. The mandatory
MVP still needs actual authorized Amoy deployment/validation, the existing
frontend/extension consumer work and resolution of any recurrence of the initial
dashboard HTTP 500 recorded below. No unconditional release-readiness or public
blockchain success is claimed. The prepared branch is for review.

## Baseline and scope

Work branch: `feature/blockchain-mvp-completion`, created from the fetched public
`integration` commit `bec0d8323ff98cb9e4e83c51f607d23d1e9ab46a`. The previous
`feature/passport-blockchain-proof` branch remains at `c8cc9fd`. No worktree was
created and no branch was merged, reset or stashed during implementation. The
starting working tree was clean; implementation ended with an uncommitted diff.

Publication follow-up: the user subsequently authorized committing and pushing
this prepared changeset. The test evidence and readiness classification remain
unchanged. No merge, shared migration or public deployment is included in that
authorization.

Developer 1 has already integrated the earlier stabilization and additional fixes
in `dcd0da4`, `8d36cd9` and `bec0d83`. This follow-up preserves that work instead
of copying the old blockchain branch over the unified backend. In particular,
middleware registration, truthful private/public status mapping, the unchanged
three-query upload regression, empty-snapshot protection, reviewed original-byte
recovery, disposable test ownership, migration preservation checks and the HTTP
acceptance harness are already present.

The existing achievement/credential/Passport services, lifecycle audit,
publication queue, PDF template, PostgreSQL operation/nonce persistence, Solidity
registry and public verification are reused. No competing model, issuance path,
verification system or renderer was added. No React implementation was changed.

## Corrections

1. **Stale current verification during a concurrent version update.** Independent
   chain verification could succeed, then a newer version could appear between
   the identity-pointer read and the final institutional registry assessment.
   The old version's registry status became OUTDATED but its nested
   `blockchain_verified` flag could remain true. The current verdict now also
   requires that final registry assessment to be VALID and latest. The returned
   latest-version number uses that same newer assessment. Historical chain
   integrity remains available; no database lock spans an RPC call.
2. **Authoritative network/explorer metadata.** The existing proof DTO now adds
   `network`, `transaction_explorer_url` and `required_confirmations`. Explorer
   links use only the fixed Amoy HTTPS origin and an exactly validated 32-byte
   transaction hash on chain 80002. Local Anvil has no public explorer link.
   Pending work can expose a saved hash/link without claiming confirmation.
   Missing configuration yields null network/link values. No RPC credentials,
   request-provided URLs or signing material enter the response.
3. **HTTP test-server cleanup.** Its serving thread now closes its own Django
   connections in a `finally` block. Main-thread connection cleanup cannot close
   a connection belonging to that thread after a failed request. This preserves
   the existing assertions and run-owned database disposal safeguards. Future
   unexpected HTTP 500 assertions include test-only exception types and stack
   locations, without exception messages, request bodies, locals or secrets.

The current-proof race was reproduced against the pre-fix service with an actual
confirmed Anvil transaction and a real PostgreSQL version publication. The old
code returned true for `blockchain_verified` despite registry status OUTDATED.
The initial new-test run also found a synthetic fixture with a non-BTU email;
the fixture now uses a BTU-domain address. No security assertion was relaxed.

## Changed files

- `backend/apps/blockchain/services.py`: final registry currency guard and
  additive metadata for the existing proof paths.
- `backend/apps/blockchain/metadata.py`: fixed network labels and explorer links.
- `backend/apps/blockchain/test_mvp_integration.py`: concurrent-version
  regression, metadata safety, pending/unconfigured states and consistency
  across Student, dashboard, PDF, public reference/version/upload/proof APIs.
- `blockchain/API_CONTRACT.md`: exact new field semantics and consumer guidance.
- `blockchain/API_EXAMPLES.json`: updated illustrative local response shapes;
  these examples are not deployment evidence.
- `blockchain/README.md`: integrated middleware and current-proof behavior.
- `blockchain/MVP_INTEGRATION_2026-10-27.md`: this evidence and handoff.
- `blockchain/TEST_REPORT.md`: current follow-up reference and results.
- `ops/test_backend_chain_e2e.py`: close the serving thread's database
  connections on both normal shutdown and failure.

## Validation

No prior developer's test totals are counted as fresh evidence from this session.
Counts below overlap and must not be summed as distinct tests.

| Check | Result |
| --- | --- |
| Existing recovery/status and PostgreSQL verification baseline | 30 passed in 137.559 seconds |
| New focused race/metadata tests | 4 passed in 67.548 seconds |
| Foundry/Solidity | 11 passed, 0 failed, 0 skipped |
| Recompiled ABI/creation/runtime artifact | Exact match |
| Test-resource process cleanup unit checks | 6 passed |
| Actual PostgreSQL failure/interruption/existing-database safeguards | Passed; 3 local-policy tests also passed |
| Django system checks and migration drift | No issues; no changes detected |
| Full nine-application final regression | 563 passed in 1007.430 seconds; 565 discovered, only the two pre-existing legacy reference-SQL comparisons excluded |
| Initial real HTTP/Anvil lifecycle acceptance | Passed journeys 1–3; dashboard returned HTTP 500 in journey 4; database-level cleanup also found one server-thread connection, while outer owned-cluster cleanup succeeded |
| HTTP follow-up with diagnostics and server-thread cleanup | All 11 real HTTP/Anvil journeys passed; database/media/server/signer and owned cluster cleanup succeeded |
| Final normal HTTP acceptance command | All 11 real HTTP/Anvil journeys passed; all owned resource cleanup verified; command exited 0 |

The full release run covers the final application source, including the
synchronized latest-version metadata/assertion added after the focused run
began. The HTTP server's cleanup/diagnostic changes followed that run; only the
test driver changed afterward. Initial
Linux cluster startup failed before Django tests because the extracted
PostgreSQL installation needed its share directory and a writable socket path;
temporary wrappers outside the repository supply these paths. No application
test was weakened to accommodate the environment.

Environment: Python 3.13, PostgreSQL 17, web3.py 7.13.0, native Anvil/Foundry
1.7.1, Solidity 0.8.30 and OpenZeppelin 5.4.0. The combined run creates and
destroys a fresh exclusively owned PostgreSQL cluster on a dynamic loopback port,
new databases and local-only signing material. It never loads production `.env`.
Its local cluster has fsync/synchronous commit/full-page writes disabled for test
speed; these results do not certify power-loss durability. Existing clusters are
not adopted or stopped. Logs are `/tmp/btu-mvp-{baseline,race-before,focused,
release,foundry,artifact,http-diagnostic,http-final}.log` in this execution
environment.

Reproduce with the pinned Python/npm requirements and installed PostgreSQL:

```text
python -B ops/run_isolated_tests.py --backend --chain-http
npm --prefix blockchain test
npm --prefix blockchain run check
```

Set `PASSPORT_PG_BIN` to the installed PostgreSQL binary directory when needed.
This environment uses an external temporary wrapper directory for the extracted
Linux installation; normal installations do not need that wrapper. The native
Solidity compiler was selected with `SOLC_PATH=/tmp/btu-solc-0.8.30`. No shared
database, public RPC or public transaction is involved in these commands.

## Schema and operational handoff

No new migration, environment variable, route or permission is introduced by this
follow-up. The baseline still requires the already implemented migrations:

- `backend/apps/accounts/migrations/0007_alter_user_options.py`
- `backend/apps/passports/migrations/0007_passportlifecycleevent_passportpublication_and_more.py`
- `backend/apps/passports/migrations/0008_lifecycle_integrity.py`
- `backend/apps/blockchain/migrations/0001_initial.py`
- `backend/apps/blockchain/migrations/0002_proof_integrity.py`

Follow `ops/BACKEND_MIGRATION_RUNBOOK.md`: back up and rehearse first, measure the
name/salt backfill and DDL locks, stop old workers, preserve all IDs/snapshots/PDF
bytes, and use reviewed forward recovery after immutable history exists. No
shared Neon data or persistent development database was modified here.

Use the existing instructions in `blockchain/README.md` to start Anvil, configure
Django's local policy, supervise PDF/chain workers, deploy to Amoy and run the
independent PDF/transaction checker. Local chain ID is 31337; public Amoy is
80002. Mainnet is rejected. The registry uses delayed two-step administration
and separate issuer authorization; Students do not need wallets. The BTU
website-publication gate remains removed.

## Required external acceptance and coordination

- **Amoy:** no RPC, deployed registry, approved issuer address or signing-key path
  is configured in the local process/backend configuration (presence-only check;
  no values were output). No public deployment address or transaction exists
  from this work. Obtain an approved HTTPS RPC, separately controlled admin and
  issuer wallets, test POL, reviewed deployment configuration and explicit
  broadcast authorization. Then run the documented issuance, replacement,
  revocation, PDF integrity and outage/recovery acceptance on actual Amoy.
- **Frontend owner:** `frontend/src/student/contracts.ts` and its adapters must
  retain proof/lifecycle metadata; `frontend/src/verification/contracts.ts` must
  accept pending/replaced/unissued states and the nested proof;
  `frontend/src/auth/contracts.ts` must retain the two explicit lifecycle
  capabilities; `frontend/src/admin/live/PassportPage.tsx` must select ACTIVE by
  default and label explicit history. No page redesign is needed. See
  `ops/BACKEND_API_HANDOFF.md`. Student website, Classroom viewer and extension
  should consume the same self-scoped Passport/PDF endpoints. An extension must
  show the Passport only; no extension implementation or browser acceptance is
  claimed by these backend tests.
- **Developer 1/operator:** review the narrow blockchain diff and existing shared
  migration/worker runbook. Keep fixed BTU issuer trust, exact registrar grants,
  current-only Student routes, CSRF, public throttling/no-store and immutable
  history. No production files outside the blockchain package or schema changes
  are introduced in this follow-up; the shared HTTP test driver has only the
  cleanup/diagnostic changes described above.
- **Unexplained initial HTTP failure:** the first combined run returned HTTP 500
  from `GET /api/student/dashboard/` after the second approved completion. No
  application exception stack was captured then. The diagnostic rerun passed
  all 11 journeys; the subsequent normal driver also passed all 11 with the same
  application code. No root cause or application fix for that 500 is claimed.
  The separate server-thread cleanup defect is corrected; diagnostic capture
  now preserves sanitized stack locations on any recurrence. Developer 1 should
  investigate any recurrence under combined-suite/staging load before release,
  starting from the existing dashboard adapter in `backend/apps/api/views.py`.
- **Recovery limitation:** an original transaction may be inspected and safely
  rebroadcast; fees/nonces/signatures are never rewritten. Irrecoverably
  underpriced or externally consumed nonces still require a reviewed forward
  transaction-attempt design. Keep the issuer exclusively operated. Local tests
  cannot certify public mempool behavior or power-loss durability.

The mandatory blockchain MVP remains incomplete until public Amoy and actual
client acceptance succeed. Local confirmation must never be presented as Amoy
deployment or as completion of the website/extension.
