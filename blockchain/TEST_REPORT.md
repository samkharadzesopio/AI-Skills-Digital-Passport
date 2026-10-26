# Local blockchain integration acceptance

Date: 2026-10-26. Branch: `feature/passport-blockchain-proof`.

This is local implementation evidence, not public Polygon Amoy or institutional approval. No shared Neon migration, public contract deployment, push or merge was performed.

## Environment and scope

- Disposable loopback PostgreSQL 17 databases using `apps.integrations.postgres_test_settings`, which ignores production `.env` and refuses remote database targets.
- Native Anvil 1.7.1 subprocesses with fresh runtime-only test mnemonics, actual deployed Solidity contracts and real signed local EVM transactions. No database-only chain simulator or fabricated transaction receipts.
- Foundry 1.7.1, native Solidity 0.8.30, OpenZeppelin 5.4.0 and web3.py 7.13.0. Pinned contract artifact reproduced from source.
- Synthetic registrar evidence and BTU HTTPS approval responses in tests. Actual BTU domain publication, registrar operations and public Amoy connectivity were not tested.
- Existing PDF renderer, fonts, stamps, storage repository, achievement/credential services and private/public Django APIs exercised. No alternative PDF template or duplicated credential issuance service.

## Results

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
4. Publish the matching, time-bounded registry declaration on BTU's real HTTPS well-known endpoint; configure restrictive signing-key storage and supervised PDF/chain workers.
5. Reproduce completion, replacement, revocation, outage/restart and changed-PDF checks on Amoy. Independently validate canonical receipts/events and actual PDF commitments via another RPC or explorer.
6. Wire and accept the real React/Chrome/Classroom viewers against `API_CONTRACT.md`, including stale-cache removal, current-only identity and truthful pending/error states. Chrome implementation remains separate; no browser/extension acceptance is claimed here.

Until these steps pass, the mandatory public blockchain MVP is **not complete**.
