# Phase 1 blockchain audit — 28 October 2026

Assigned branch: `feature/passport-blockchain-proof`. Initial clean HEAD:
`e88127d4f71e6d0a4a2795cc34d43c0b65bc0386`. One existing worktree was found;
none was created, switched, reset, stashed or overwritten. Latest integration
was fetched read-only at `96ec681b4ae75fd11875386e154e7b1208d04daf` for comparison. No commit, merge, push,
public deployment/transaction or shared Neon migration is part of this phase.

## Initial findings by severity

- **Medium correctness defect, fixed:** an authorized issuer could call
  `replacePassport(previousKey, bytes32(0))`. The contract permanently cancelled
  the previous key even though zero can never receive a commitment. The Django
  path derives nonzero hashed keys, so this is an on-chain input invariant
  defect, not an unauthenticated API escalation. The new Solidity regression
  failed against the original contract, then passed after the one-line fix.
- **Operational constraint, retained:** signed operations use immutable legacy
  EIP-155 transactions. They are valid on EIP-1559 networks, but the worker does
  not construct type-2 envelopes, automatically bump fees, replace at the same
  nonce or cancel transactions. An underpriced/dropped/competing nonce remains
  tracked and requires the existing inspected original-byte recovery or a
  separately reviewed forward repair. This must not be marketed as automatic
  stuck-transaction replacement.
- **Compatibility boundary, documented:** runtime bytecode is pinned exactly.
  The correction changes creation/runtime bytecode, not ABI/events. Old
  deployments remain unchanged and are rejected by the new runtime pin.
- **External acceptance gap:** no actual Amoy RPC, fee market, funded issuer,
  deployment or public confirmation is tested in this phase. Local chain
  80002 tests establish envelope/adapter behavior on Anvil, not Polygon success.
- **Inherited security caveat:** historical development signing-key/password
  fixtures are described in `ops/SECURITY_CREDENTIAL_INVESTIGATION.md`.
  Live reuse is not independently known; owners must rotate any reused real
  secret. This audit does not rewrite history or rotate deployed credentials.

No additional high/critical defect was confirmed in the reviewed paths. This
is a scoped engineering review, not a formal independent security certification.

## Exact files modified

- `blockchain/contracts/PassportRegistry.sol`: reject a zero replacement key.
- `blockchain/test/PassportRegistry.t.sol`: regression proving a rejected zero
  replacement preserves the active identity and original commitment.
- `backend/apps/blockchain/contract.json`: rebuild the pinned creation/runtime
  bytecode from the corrected source; ABI is unchanged.
- `backend/apps/blockchain/anvil_testing.py`: retain default chain 31337, allow
  explicit supported local test IDs and validate the startup handshake.
- `backend/apps/blockchain/test_phase1_audit.py`: five actual local chain-80002
  compatibility/security tests, with no public RPC.
- `blockchain/API_CONTRACT.md`: runtime transition warning; no DTO/URL changes.
- `blockchain/README.md`: link the current Phase 1 report.
- `blockchain/PHASE1_AUDIT_2026-10-28.md`: this scoped audit, evidence,
  configuration and handoff.

## Contract and transaction review

Solidity 0.8.30, Cancun EVM target, optimizer 200 runs and OpenZeppelin 5.4.0
remain pinned. The registry is not upgradeable. Its one-day, two-step
administrator transfer and issuer role remain separate; the administrator can
rotate issuer grants. Commitments/events contain only domain-separated opaque
keys and digests. Document commitments cannot be overwritten. Revoked/replaced
keys are terminal, including cancellation before a delayed old issuance.

The deployment script accepts only 31337 or 80002 and requires explicit nonzero
admin/issuer addresses. It does not silently deploy to another chain. A local
Anvil deployment needs no POL faucet. Actual Amoy gas is paid in test POL.

Provider policy permits loopback Anvil (31337/1337) or HTTPS Amoy (80002), rejects
other public chains, credentials embedded in URLs, invalid addresses/limits,
and validates the node-reported chain before use. Amoy's extended PoA header is
normalized at middleware layer zero. The fixed runtime and ABI must match the
chosen registry. No network fallback is implemented.

The worker quotes `eth_gasPrice`, checks the configured price ceiling, and signs
a fixed 250,000-gas legacy transaction. Actual operation gas estimates and used
gas are tested against that ceiling; gas estimation is not a new runtime RPC
inside a PostgreSQL lock. EIP-155 binds signatures to the exact chain ID. Price
ceilings bound cost but cannot guarantee timely Amoy inclusion. A future type-2
or same-nonce replacement design must preserve signed-attempt history and
update recovery validation; it is intentionally outside this minimal fix.

## Django, lifecycle and public security review

The existing path remains authoritative: verified achievement → credential
lifecycle event → Passport version → durable PDF publication → original PDF →
durable blockchain operation → confirmation → public verification. No duplicate
Student, skill, credential, Passport, issuer or publishing service is added.

Nonce reservation and signed bytes/hash are committed atomically before
broadcast. PostgreSQL locks/uniqueness serialize concurrent reservations.
Recovery rebroadcasts the original signed bytes only, after target, nonce,
fee, PDF and dependency checks. Lost acknowledgements, restarted workers,
pending confirmations and conflicting externally consumed nonces remain
explicit. RPC calls are outside database atomic blocks; the adapter rejects
network work within such a block.

Verification checks current chain/runtime, the exact transaction and calldata,
signer, nonce, canonical block/receipt, events, stored commitment and confirmation
depth. A saved CONFIRMED row alone cannot establish verification. Live reorg
observations preserve the original immutable receipt. Public timeouts/outages,
failed operations and misconfiguration fail closed, under the existing shared
request/worker RPC budgets. Raw provider errors, RPC URLs and keys are not
returned. A confirmed historical PDF cannot restore current credential validity
or a cancelled identity.

Approved name changes require the exact registrar grant, expected current
identity, approved evidence source and idempotency key. The old identity loses
current status immediately; the new identity has a separate public reference,
frozen legal name, version/PDF and commitment. New issuance depends on confirmed
old-key cancellation. Skills, credentials and old PDFs/audit records remain.
Student history access, authorized Admin audit access, public terminal status,
session/CSRF and exact revocation grants remain unchanged.

The raw issuer key is server-only in a restricted external file, with matching
address verification and symlink/size/permission checks. Windows equivalent
ACLs remain an operator duty. No private key or academic PII is put into React,
extension responses, on-chain calldata or committed configuration.

## Tests and evidence

All final checks below passed. These are fresh Phase 1 results, not inherited
results from the October 27 report.

| Check | Result |
|---|---|
| Defect reproduction before fix | 11 Solidity passes, 1 intended regression failure: zero replacement did not revert |
| Final Solidity/Foundry suite | 12 passed, 0 failed, 0 skipped |
| Recompiled ABI/creation/runtime comparison | Exact artifact match; ABI unchanged |
| PostgreSQL Django regression run, five selected apps | All 262 discovered tests passed in 654.392 seconds |
| New chain-80002 envelope tests | All five passed as part of the 262; not counted again |
| Real HTTP/PostgreSQL/Anvil acceptance | All 11 journeys passed |
| Resource-cleanup unit tests | 6 passed in 0.497 seconds |
| Local-profile boundary unit tests | 3 passed in 0.001 seconds |
| Actual database failure/interruption/reuse safeguards | Passed; existing database refused and preserved |
| Separate local chain-80002 lifecycle/runtime probe | Passed; gas measurements below |
| Django system checks / migration drift | No issues / no changes detected |
| Whitespace / changed-file secret patterns | Passed / no candidates in the eight changed/new files |

The 262 tests cover `apps.blockchain`, `apps.credentials`, `apps.passports`,
`apps.api` and `apps.verification`. This is a scoped regression run, not a fresh
run of every application in the repository. Authentication and integration
behavior is additionally covered by the real HTTP journeys. Those journeys
exercise OTP/session and cross-owner denial, no-evidence login, approved import
through confirmed proof, immutable version updates, exact/altered PDFs,
credential revocation, approved legal replacement with old-key cancellation,
RPC outage/worker recovery, terminal Passport revocation, CSRF/least privilege,
public privacy, logout and duplicate replay without reactivation.

No final automated test failed or remained blocked. The pre-fix red test above
is retained as defect evidence. Initial extracted PostgreSQL tool startup failed
before test execution because the external wrapper supplied a nonabsolute
executable identity; the wrapper was corrected outside the repository and the
complete test run passed. The default Solidity download host was unavailable;
the same 0.8.30 native compiler was obtained from the upstream solc-bin mirror
and SHA-256 checked against its published build manifest before use.

No assertion, timeout or exclusion was loosened. PostgreSQL 17.11, native
Foundry/Anvil 1.7.1, Solidity 0.8.30, Python 3.13 and web3.py 7.13.0 were used.
These fresh owned test clusters retained PostgreSQL's default durability
settings; the external wrapper only supplied the writable temporary Unix socket
directory. No crash/power-loss durability certification is claimed. Both
runners verified owned cluster/artifact cleanup. Logs are
`/tmp/btu-phase1-backend.log` and `/tmp/btu-phase1-http.log`; the changed-file
scan summary is `/tmp/btu-phase1-security.json`. No tracked private environment,
raw key, keystore or state filename was found. Pattern scans are limited and do
not negate the inherited historical credential caveat above.

Reproduction:

```text
npm --prefix blockchain test
npm --prefix blockchain run check
python -B blockchain/scripts/test_backend.py apps.blockchain apps.credentials apps.passports apps.api apps.verification
python -B ops/run_isolated_tests.py --chain-http
```

Set `PASSPORT_PG_BIN` to installed PostgreSQL binaries and `SOLC_PATH` to an
installed verified Solidity 0.8.30 binary when automatic compiler downloads are
unavailable. On Windows use `npm.cmd` and `npm.cmd ci --ignore-scripts`. Test
runners create and remove exclusively owned loopback PostgreSQL clusters and
Anvil nodes; they never load the production environment or adopt old clusters.

`test_phase1_audit.py` uses real Anvil transactions with local chain ID 80002
and injects that loopback transport into the Amoy adapter. It tests legacy
EIP-155 signing on an EIP-1559 chain, actual gas estimation/usage, three-block
confirmation, wrong-chain rejection, fee ceiling and cross-chain replay
rejection. Its synthetic HTTPS policy endpoint is never contacted. Existing
tests separately exercise extended PoA headers and bounded failing transports.

A separate real-transaction probe used a fresh owned Anvil node with chain ID
80002, deployed the corrected contract and confirmed each operation with three
blocks. It then deployed the previous artifact on that node and confirmed the
new adapter rejects it with `UNAPPROVED_CONTRACT_CODE`. No public RPC was used.
Its JSON evidence is `/tmp/btu-phase1-rehearsal.json`; the node was stopped.

| Local operation | Estimated gas | Actual gas used |
|---|---:|---:|
| Initial issuance | 139,889 | 139,889 |
| Old-key replacement | 34,153 | 34,153 |
| Separate new-identity issuance | 139,877 | 139,877 |
| New-identity revocation | 30,971 | 30,971 |

Corrected registry deployment used 1,169,166 gas. These are local measurements,
not public Amoy fees or a promise of inclusion cost. Both operation histories
remained verifiable with terminal REPLACED/REVOKED chain state, respectively.

## Deployment configuration (values stay private)

- `PASSPORT_BLOCKCHAIN_ENABLED=true` only after reviewed configuration.
- `PASSPORT_BLOCKCHAIN_RPC_URL`: actual loopback Anvil URL, or operator-approved
  HTTPS Amoy URL; no supplied production credential is recorded here.
- `PASSPORT_BLOCKCHAIN_CHAIN_ID`: 31337 for the primary local rehearsal,
  80002 for a separately authorized Amoy deployment.
- `PASSPORT_BLOCKCHAIN_CONTRACT_ADDRESS`: actual corrected deployment address.
- `PASSPORT_BLOCKCHAIN_ISSUER_ADDRESS`: actually authorized issuer address.
- `PASSPORT_BLOCKCHAIN_SIGNING_KEY_FILE`: restricted absolute path outside Git;
  never a literal private key, browser setting or sample credential.
- `PASSPORT_BLOCKCHAIN_CONFIRMATIONS`: default 3; an explicit institutional
  testnet confirmation policy may choose a supported value from 1 to 64.
- `PASSPORT_BLOCKCHAIN_MAX_GAS_PRICE_WEI`: default 50,000,000,000; review actual
  Amoy fees/cost limits before deployment, without bypassing the configured cap.
- `BTU_CLASSROOM_ISSUER_REFERENCE=BTU-UNIVERSITY` and
  `VERIFICATION_TRUSTED_ISSUER_REFERENCES=BTU-UNIVERSITY`, backed by the existing
  trusted database issuer provisioned through its authorized audited service.
- `PASSPORT_IDENTITY_EVIDENCE_SOURCES`: explicitly approved registrar sources;
  `BTU_REGISTRAR` is a controlled synthetic local demonstration policy.
- `BTU_REGISTRY_ADMIN` and `BTU_REGISTRY_ISSUER`: public role addresses used only
  by the existing deployment script. Use separate local admin/issuer custody.

Existing secure Django/auth, database and email configuration is still
required. The guarded local development profile requires DEBUG/local opt-in,
loopback PostgreSQL named `btu_passport_local` and explicit Student status policy.
Secrets and local state must stay outside Git.

## Integration and next-phase boundary

No Django models, migrations, shared settings, Passport services, unrelated
frontend files or API response fields are changed. Developer 1 must preserve
the existing lifecycle migrations/immutability guards and request RPC-budget
middleware when integrating. The integration branch's additional assessment
race tests were reviewed read-only; this phase does not merge them.

The newer frontend branches are separate from this blockchain checkout.
Their API/visual/browser acceptance is not established by these backend tests.
Keep pending/unavailable, current verification and historical authenticity
distinct, and label local Anvil honestly. No university website publication
gate is introduced.

The updated artifact requires a fresh isolated registry/database rehearsal.
**Never reset an existing database/node, alter immutable saved proof targets,
or merely change its configured registry address to force old proofs to pass.**
Existing deployments and historical verifiers need a reviewed transition plan
before adopting new bytecode. There is no database migration in this fix.

**Phase 1 complete; ready for Phase 2 isolated Anvil rehearsal with the corrected
registry and a fresh disposable database.** Relevant automated tests pass,
configuration is documented and no further blockchain-owned defect was
confirmed in this review. Existing-deployment adoption remains conditional on
the explicit registry/history transition above. Public Amoy compatibility is
locally exercised but not publicly accepted; real RPC/fees/funding/roles and an
explicit deployment authorization are required in a later phase.

Phase 2 must be started separately. At Phase 1 reporting, changes remained
uncommitted on the assigned branch for review. The user subsequently authorized
committing and pushing this tested changeset to `feature/passport-blockchain-proof`.
That publication does not authorize Phase 2, a merge or any public deployment.
No Developer 1 schema rewrite or new migration is required by this fix; their
deployment/history coordination and frontend acceptance remain separate.
