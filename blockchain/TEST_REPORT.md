# Local blockchain integration acceptance

Updated: 2026-10-27. Reviewed baseline: `044264f`, `feature/passport-blockchain-proof`. Publication of the reviewed stabilization changes was subsequently authorized; see Git history for the resulting commit. The NOT READY classification and recorded test results are unchanged.

This report records local implementation evidence. The initial implementation was pushed as `044264f`; no shared Neon migration, public contract deployment or merge was performed. Results below that predate the website-gate removal are historical runs, not a claim that the revised suite was rerun in full.

## Environment and scope

- Disposable loopback PostgreSQL 17 databases using `apps.integrations.postgres_test_settings`, which ignores production `.env` and refuses remote database targets.
- Native Anvil 1.7.1 subprocesses with fresh runtime-only test mnemonics, actual deployed Solidity contracts and real signed local EVM transactions. No database-only chain simulator or fabricated transaction receipts.
- Foundry 1.7.1, native Solidity 0.8.30, OpenZeppelin 5.4.0 and web3.py 7.13.0. Pinned contract artifact reproduced from source.
- Synthetic registrar evidence and trusted configured issuer records in tests; actual registrar operations and public Amoy connectivity were not tested. The earlier website-publication policy and its HTTP fixtures have been removed.
- Existing PDF renderer, fonts, stamps, storage repository, achievement/credential services and private/public Django APIs exercised. No alternative PDF template or duplicated credential issuance service.

## Results

### October 27 pre-integration stabilization: NOT READY

See `STABILIZATION_HANDOFF_2026-10-27.md` for exact changed paths, conflicts against cc74833, reviewed shared patches and migration considerations. Fresh owned disposable PostgreSQL and native Anvil were used; no shared database or public network was touched.

- Foundry: 11 passed; artifact rebuild exactly matches the committed ABI/bytecode.
- Broad checkout backend run: 531 tests in 446.911 s, 529 passed and 2 failed; 533 discovered, 2 pre-existing legacy SQL comparisons excluded.
- Final targeted run after refinements: 16 tests in 21.587 s, 15 passed and 1 failed. All 13 new stabilization cases, the independent CLI and the corrected PDF idempotency regression passed.
- Supplemental final transport checks: 6 passed in 0.108 s, including the additional connection-cleanup error/deadline-isolation case. The current stabilization module therefore contains 14 cases, covered across these overlapping runs.
- Remaining failure: `PostgreSQLVerificationTests.test_real_pdf_uses_existing_repository_and_no_private_response`, 4 queries versus the unchanged required 3. The zero-query already-validated-document fast path is tested; Developer 1 must pass its `known_document=True` hint from the shared repository-backed upload verifier. That caller was not overwritten in this task.
- Request-wide middleware registration, private failed/configuration-state mapping, integration test labels and frontend DTO/currency handling also require integration-owner changes before approval.
- No migration/model drift; Django checks and whitespace checks passed. No test assertion or query budget was weakened.

The broad run predates the last metadata/connection-cleanup refinements; the final targeted run covers those changes. These are overlapping runs, not a combined count. No target-only React/HTTP or public Amoy acceptance is claimed.

### Historical initial implementation runs

| Check | Result |
|---|---|
| Foundry contract tests | 11 passed, 0 failed, 0 skipped |
| Rebuild against committed ABI/creation/runtime bytecode | Exact match |
| Combined backend regression suite | 523 passed in 1275.783 seconds; 525 discovered, 2 existing legacy SQL comparisons excluded |
| Main Anvil/PostgreSQL acceptance run | 60 passed in 498.780 seconds |
| Expanded final Anvil/migration/public-verification acceptance | 73 passed; 1 process-deadline error in 517.287 seconds, resolved by the rerun below |
| Independent verifier after bounded startup-deadline adjustment | 1 passed in 21.505 seconds |
| Focused credential validity/reference checks | 15 passed in 75.193 seconds |
| Disabled transport/unknown-reference check | 1 passed in 2.642 seconds |
| Django system check | No issues |
| Migration/model drift check | No changes detected |
| Whitespace check | Passed |

The expanded 74-test acceptance run passed 73 tests and hit one `subprocess.TimeoutExpired` at the independent verifier's 20-second process deadline while running beside the combined suite. No proof-validity assertion failed. The test now permits a bounded 60 seconds for fresh interpreter/web3 startup; individual production RPC requests remain limited to five seconds. Its separate rerun passed with all proof assertions retained. The other 73 final acceptance checks were not repeated after this test-only deadline adjustment.

The combined regression run started before the final bounded-credential-validation and disabled-transport refinements; the expanded acceptance run and targeted checks cover those final changes. Counts overlap; they are separate runs, not an aggregate number of distinct tests.

The combined runner deliberately excludes the two existing legacy reference-`schema.sql` comparison tests in `apps.skills.tests` and `apps.students.tests`. Django migrations, migration preservation and PostgreSQL concurrency checks remain enabled. Registry-only legacy regression tests use their existing isolated settings; the new blockchain acceptance tests explicitly enforce chain validation.

## Behaviors covered

- Trusted simulated Classroom completion creates existing achievements and credentials, publishes the existing official PDF, and obtains a confirmed, independently validated local chain commitment.
- Authorized legal-name replacement immediately cancels the old identity, retains the Student/skills/credentials, issues a distinct permanent identity/version/PDF, confirms old-key cancellation, then confirms the separate new commitment.
- Old public references and uploaded old PDFs return REPLACED, historical chain authenticity remains inspectable, and Student PDF/history routes cannot expose cancelled identities as current. Private registrar history and administrative downloads retain audit records.
- Session authentication, CSRF, exact registrar capability, approved evidence source, replay, concurrent duplicate/conflicting administrators and credential issuance during replacement.
- RPC outages, pending confirmation depth, worker crashes before/after broadcast, retry exhaustion/recovery, durable signed-byte/nonce reservations, receipt/call/event tampering, canonical reorganization and independent read-only proof verification.
- Revoked credentials cannot retain a current badge while refresh is pending. Exceeding bounded credential validation cannot be mistaken for an empty issued snapshot.
- Missing chain configuration does not undo approved cancellation: the immutable lifecycle event retains the intent, and later workers recover cancellation and anchoring.
- Forward migration preserves prior Passport identity, snapshot hashes and exact PDF bytes; unsafe downgrade cannot discard cancelled identities or retained chain receipts.
- No names, emails, Student identifiers, public UUID bytes or PDF contents in contract calldata. Issuer key rotation preserves historical proofs; administrator rotation requires delayed acceptance.

## Required before public acceptance

1. Developer 1 reviews the Student-to-Passport relationship evolution, PostgreSQL guards, backfill and deployment/rollback plan in `README.md`. Stage and back up the shared schema before any authorized migration; stop old workers before deploying this relationship change.
2. BTU approves separate administrator/deployer/issuer custody and provisions the existing fixed database issuer through its authorized service. No implicit issuer is created.
3. Supply an approved Amoy RPC and funded test POL wallets. Review deployment simulation and explicitly authorize broadcast. Record actual chain 80002 receipts, registry runtime hash and role assignments.
4. Configure restrictive signing-key storage and supervised PDF/chain workers. No BTU website publication is required.
5. Reproduce completion, replacement, revocation, outage/restart and changed-PDF checks on Amoy. Independently validate canonical receipts/events and actual PDF commitments via another RPC or explorer.
6. Wire and accept the real React/Chrome/Classroom viewers against `API_CONTRACT.md`, including stale-cache removal, current-only identity and truthful pending/error states. Chrome implementation remains separate; no browser/extension acceptance is claimed here.

Until these steps pass, the mandatory public blockchain MVP is **not complete**.
