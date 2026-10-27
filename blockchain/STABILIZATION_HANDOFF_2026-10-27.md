# Blockchain pre-integration stabilization — 27 October 2026

Branch HEAD: `044264f893dbbfd0d0d44cc2a2af562a1e8df5ea` (`feature/passport-blockchain-proof`). Target inspected read-only: `cc74833d792f64a9c37764e25cff7108aa524eea` (`integration`). No branch/worktree creation or switching, merge, commit, push, shared migration or public transaction was performed in this stabilization session.

Publication follow-up: the user subsequently authorized committing and pushing this prepared changeset for review. The baseline and test evidence below describe the stabilization review; its NOT READY classification remains in force. No merge, shared migration or public deployment was authorized by that publication request.

## Classification: NOT READY

Blockchain-owned corrections are implemented and locally tested, but integration approval remains blocked by shared request-budget/private-status/document-caller wiring and target-client contract incompatibilities below. One existing upload-verification query-budget assertion remains failing until that caller is connected. The target has not been combined or tested with this branch. This is not a declaration that Polygon Amoy is deployed or the complete website is accepted.

The user's earlier removal of the BTU website-publication gate was already uncommitted when this task began. It is preserved. The prior working diff was saved at `/tmp/btu-pre-stabilization-snapshot/uncommitted.patch`; no uncommitted file was restored or overwritten from another branch. Existing shared-file edits from that removal remain; no further stabilization edits were made to shared settings, serializers, Passport lifecycle/schema or React files.

## Problems corrected

- Explicit validated Anvil/Amoy provider selection; mainnet, invalid ports, unsafe URLs and invalid numeric/address policies fail before transport. The independent verifier now uses the same factory.
- Amoy PoA header normalization at middleware layer zero, including a unit case with a 97-byte header. No real Amoy RPC was called.
- A six-second RPC verification budget across issuance/replacement dependencies, a 25-second worker-operation budget, bounded 8 MiB streaming responses, per-call five-second budgets and one-second socket inactivity limits. Redirects and transparent HTTP retries are disabled. Timeout/availability responses are sanitized and never trust a saved CONFIRMED row.
- Exact transaction hash, chain ID and reserved nonce comparisons, alongside existing recipient/signer/calldata/log/commitment/canonical-block/confirmation checks.
- Signing observations commit with nonce reservations. Known pending/mined transactions are not repeatedly broadcast. Stuck submissions stay tracked with an explicit review alarm; an externally consumed nonce fails for review without re-signing or resetting the ledger. Actual later confirmation remains recoverable.
- Read-only `inspect_blockchain_operation`, with optional bounded chain reads, never loads a signer or broadcasts.
- Public failed/misconfigured verification is UNVERIFIABLE rather than silently pending. Nested `institutional_issuer_approved`, `assessed_at`, `operation_state` and `operator_review_required` separate institutional provisioning, live evidence and operational state. The signed transaction hash remains available during outages/pending confirmation.
- The approved website-gate removal has no substitute web/DNS approval. Trust uses the existing fixed provisioned BTU issuer and server allowlist plus the configured registry and actual authorized on-chain issuance. Historical issuer rotation remains supported.

## Required integration changes owned by Developer 1 / client owners

1. Register `apps.blockchain.middleware.BlockchainRPCBudgetMiddleware` in shared `config/settings.py` middleware. Without this, each proof is bounded but an admin list can spend one budget per Passport. Keep RPC outside ATOMIC_REQUESTS/explicit database transactions; the adapter rejects calls inside transactions.
2. In shared `apps/api/serializers.py::PassportSerializer.get_status`, retain lifecycle/credential terminal handling, but map only nested PENDING_BLOCKCHAIN to a pending root. FAILED and NOT_CONFIGURED must map to UNVERIFIABLE. That shared serializer still retains its earlier mapping; this task did not overwrite it. The earlier uncommitted website-gate removal in that file must be retained.
3. Preserve integration's owned disposable test harness and add `apps.blockchain` to `ops/run_isolated_tests.py`'s explicit backend labels. Install the pinned blockchain npm tools before the backend job; add Foundry tests and artifact comparison. Do not replace the new integration harness with this branch's older loopback-only `ops/test_backend.sh`.
4. Update frontend explicit allowlists/adapters and acceptance fixtures for nested blockchain facts and public PENDING_BLOCKCHAIN/REPLACED. At cc74833, `frontend/src/verification/contracts.ts` excludes those statuses; Student/PDF adapters discard the optional blockchain DTO. Keep existing source/identity/credential/current-version facts distinct. No React code was changed here.
5. Resolve the shared route/test conflicts below, preserving the target's admin read endpoints plus registrar/lifecycle routes. Run the combined backend and existing Student/Admin/public HTTP acceptance against a new disposable cluster after the authorized integration step. Those combined tests cannot be claimed from this checkout.
6. In `backend/apps/verification/document_service.py`, after the existing repository has found the issued PDF, pass `known_document=True` to `document_proof(document['document_id'])`. The owned fast path avoids redundant disabled-transport existence lookup, with no enabled-chain validation bypass. Keep the existing three-query assertion unchanged. The current shared caller does not pass the hint and still executes four queries; this is an explicit failing integration dependency. Do not source this hint from HTTP input.

The target's `frontend/src/admin/live/PassportPage.tsx` defaults to `rows[0]` for a Student. Once historical permanent identities exist, prefer ACTIVE for the default current view and require explicit selection/lifecycle labeling for history. Preserve authorized historical PDF access and its audit trail.

Concrete shared edits for Developer 1 to review (not applied here):

```python
# config/settings.py: add to the existing MIDDLEWARE list
'apps.blockchain.middleware.BlockchainRPCBudgetMiddleware',

# apps/api/serializers.py: final pending/error branch after terminal handling
return 'PENDING_BLOCKCHAIN' if proof.get('status') == 'PENDING_BLOCKCHAIN' else 'UNVERIFIABLE'

# apps/verification/document_service.py: after issued-document repository lookup
proof = document_proof(document['document_id'], known_document=True)
```

## Migration considerations

No new migration is introduced by stabilization. SIGNED observations use the existing table. The original branch still includes accounts 0007, passports 0007/0008 and blockchain 0001/0002. Developer 1 must review the one-to-one-to-history relationship, ACTIVE-only uniqueness, original identity/name/date backfill and immutable PostgreSQL guards. Preserve the original versions/PDF bytes and existing Student/credential ownership. Stop old workers before a staged schema/code deployment; do not apply to shared Neon from this work.

Downgrade is refused after retained proofs/lifecycle history exist. A consumed-nonce or fee-replacement repair must preserve signed evidence in a reviewed forward design; do not loosen existing receipt/nonce triggers. If integration acquires migrations after the inspected target, rebase migration dependencies during authorized integration, not by deleting or renumbering applied history.

## Likely conflicts and semantic coordination

Both branches changed these paths relative to common base 05d0b1f: `.gitignore`, `backend/.env.example`, `backend/apps/api/urls.py`, `backend/apps/api/test_pdf.py`, `ops/test_backend.sh`. These are overlapping edits, not a claim of an executed merge or exact textual conflict count.

Additional semantic review: shared `backend/config/settings.py`, `backend/config/foundation_test_settings.py`, target `backend/config/foundation_test_runner.py`/`backend/config/disposable_tests.py`, `backend/apps/accounts/authorization.py`, Passport model/services/lifecycle/publication, API query/serializer/current-Passport helpers and the target's frontend adapters. Preserve target authorization and disposable-database safeguards. Keep the registrar capabilities and inactive-identity filtering introduced by the original feature.

## Remaining risks / external acceptance

- No public Amoy RPC, deployment, funding or network acceptance. Local Anvil cannot establish public testnet success. Production must report chain 80002 and the actual approved deployed registry/roles.
- No automatic fee bump, cancellation or nonce reassignment. A long-underpriced transaction can block later nonces until reviewed; this is surfaced, retained and safely retried rather than silently replaced. Use an exclusively operated signer and drain queued work before key rotation.
- RPC budgets check transport reads and share nested deadlines; OS/DNS resolution and scheduling can extend wall-clock time. The integration middleware and existing API-client timeout/cancellation behavior must be accepted together. Monitor request latency and worker health.
- Existing private root-state ambiguity and multiple-proof request latency remain until Developer 1 applies the required narrow shared changes above. They are readiness blockers, not hidden as test success.
- Institution approval reflects configured issuer-provisioning policy, not an independently published university-domain identity claim. Keep administrator custody and institutional provisioning controlled. Windows signing-key ACLs remain an operator responsibility.
- Existing current-identity, legal correction, revocation, historical authenticity and credential validity checks remain mandatory; a confirmed historical commitment never restores a cancelled identity or revoked credential.

## Tests and exact changed paths

The broad checkout regression suite does not include unmerged target-only React/HTTP integrations.

| Check | Exact result |
|---|---|
| Initial new stabilization tests | 10 passed in 14.498 s |
| Broad checkout backend regression | 531 ran in 446.911 s: 529 passed, 2 failed; 533 discovered, 2 existing legacy reference-SQL comparisons excluded |
| Final targeted checks on the refined code | 16 ran in 21.587 s: 15 passed, 1 failed |
| Supplemental final provider/cleanup checks | 6 passed in 0.108 s; includes an additional cleanup-error/deadline-isolation case |
| Foundry | 11 passed, 0 failed, 0 skipped |
| Recompiled ABI/creation/runtime artifact comparison | Exact match |
| `makemigrations --check --dry-run` | No changes detected |
| Django system checks / whitespace | No issues / passed |

The broad run preceded final metadata/transport-cleanup refinements. The final targeted run includes the 13 then-existing stabilization tests, the independent CLI, and both originally failing regressions. Six provider checks subsequently passed after adding cleanup-error isolation, covering the final transport code. The PDF generation/status equality failure was fixed: unconfigured assessments now return a stable null timestamp. The remaining failure is exactly `apps.verification.test_postgres_verification.PostgreSQLVerificationTests.test_real_pdf_uses_existing_repository_and_no_private_response`: **4 queries versus the unchanged required 3**. Its fourth query is the redundant disabled-transport document-existence lookup. The separately tested `known_document=True` path uses zero queries; the shared caller change above is deliberately left to Developer 1. No assertions or query budgets were relaxed.

Testing used a newly initialized, exclusively owned temporary PostgreSQL 17 cluster on a dynamically chosen loopback port and fresh Django test databases. No production `.env` was loaded. Native Anvil subprocesses generated fresh local-only keys and actual local transactions. PoA header/HTTP stream limits are isolated transport unit fixtures, not public Amoy acceptance. The disposable cluster used fsync disabled for test speed; these results do not certify hardware/power-loss durability.

Broad labels: `apps.blockchain apps.api apps.integrations apps.skills apps.credentials apps.passports apps.students apps.accounts apps.verification`, with `apps.integrations.postgres_test_settings`. Final labels: `apps.blockchain.test_stabilization`, the independent-CLI case, and the two full regression test IDs named in the logs. Test logs are `/tmp/btu-stabilization-{focused,regression,final-checks-v3,foundry,artifact,migrations}.log`. Counts overlap and must not be added as unique-test totals.

Complete working-tree delta versus 044264f (including the preserved earlier website-gate removal):

| Status | Path |
|---|---|
| A | `backend/apps/blockchain/management/commands/inspect_blockchain_operation.py` |
| A | `backend/apps/blockchain/middleware.py` |
| A | `backend/apps/blockchain/rpc.py` |
| A | `backend/apps/blockchain/test_stabilization.py` |
| A | `blockchain/API_EXAMPLES.json` |
| A | `blockchain/STABILIZATION_HANDOFF_2026-10-27.md` |
| D | `backend/apps/blockchain/authority.py` |
| D | `backend/apps/blockchain/test_authority.py` |
| D | `blockchain/scripts/issuer_declaration.py` |
| M | `backend/.env.example` |
| M | `backend/apps/api/serializers.py` |
| M | `backend/apps/blockchain/chain.py` |
| M | `backend/apps/blockchain/policy.py` |
| M | `backend/apps/blockchain/services.py` |
| M | `backend/apps/blockchain/test_lifecycle.py` |
| M | `backend/apps/blockchain/tests.py` |
| M | `backend/apps/verification/blockchain_policy.py` |
| M | `backend/config/settings.py` |
| M | `blockchain/API_CONTRACT.md` |
| M | `blockchain/README.md` |
| M | `blockchain/TEST_REPORT.md` |
| M | `blockchain/scripts/verify_transaction.py` |
