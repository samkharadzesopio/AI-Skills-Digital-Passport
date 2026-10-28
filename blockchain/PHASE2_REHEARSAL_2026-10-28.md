# Phase 2 — isolated Anvil deployment and lifecycle rehearsal

Baseline: `71be42d3fea153649de7de494cc720e0955a3314`, on
`feature/passport-blockchain-proof`. Initial working tree was clean. No branch
switch, worktree creation, merge, commit, push, shared Neon access, frontend
design change or public transaction is part of this rehearsal.

## Reproduce the complete disposable rehearsal

Prerequisites: the repository's Python requirements/virtual environment, Node,
PostgreSQL binaries (`initdb`, `pg_ctl`), and the pinned Foundry/Anvil npm tools.
No production `.env`, public wallet, faucet tokens or external RPC is needed.
From the repository root:

```text
python -m pip install -r requirements-blockchain-test.txt
npm --prefix blockchain ci --ignore-scripts
npm --prefix blockchain test
npm --prefix blockchain run check
python -B ops/run_isolated_tests.py --chain-http
python -B blockchain/scripts/test_backend.py apps.blockchain apps.credentials apps.passports apps.api apps.verification
```

On Windows use `npm.cmd`, set `$env:PASSPORT_PG_BIN` to the actual PostgreSQL
`bin` directory, and activate the existing virtual environment. Set `SOLC_PATH`
only if an installed verified native Solidity 0.8.30 compiler must be selected.
The cloud execution uses `/tmp/btu-phase1-tools/pg-bin` for extracted PostgreSQL
17.11 and `/tmp/btu-phase1-tools/solc-0.8.30`; these are environment-specific
paths, not production configuration.

The existing launcher initializes its own temporary PostgreSQL cluster at a
free loopback port, creates its own test database and migrations, and starts the
existing native Anvil helper with newly generated local-only accounts. It
deploys `PassportRegistry` using the committed ABI/bytecode and configures Django
through isolated test settings. Neither an old node nor an existing database is
adopted. No deployment address is hardcoded into application configuration.

The shared HTTP test's existing test fixture creates the authorized database
issuer and synthetic records using the existing domain services. Actual HTTP
requests then exercise OTP/session/CSRF, approved Excel completion import,
verified achievements, credential issuance and automatic Passport versioning.
The same publication and blockchain commands used operationally drain the
persistent queues. Issued PDF bytes come from the existing authenticated PDF
API; actual JSON-RPC transactions must confirm before public verification can
succeed. This HTTP rehearsal requires three confirmations. Test scheduling mines
real local blocks and makes retry jobs due; it never mocks a receipt, returns a
fabricated confirmation or changes signed bytes/nonces.

The suite records `LOCAL_DEPLOYMENT_EVIDENCE` in stdout, containing only local
public deployment/transaction data and independent check results. The checked
rehearsal's public-only extract is `PHASE2_LOCAL_EVIDENCE.json`. These ephemeral
addresses/hashes identify this run; they are not durable production endpoints.

## Independent verification

The observer has its own `Web3.HTTPProvider`, separate from the worker/backend
provider. It checks the node's chain, exact runtime bytecode, default admin,
authorized issuer and successful deployment receipt. For issuance and terminal
lifecycle states it reads actual contract storage, canonical receipts and block
confirmations, compares the stored opaque keys/digest/issuer with the public API,
and recomputes the domain-separated salted commitment. Initial/current and
replacement PDFs are also compared with actual downloaded bytes.

This independently checks chain facts against the API; it is not a second
consensus network or an external institutional trust attestation. The existing
independent CLI additionally runs in a separate interpreter without a database
or signing key, as part of the Django regression suite:

```text
python blockchain/scripts/verify_transaction.py --rpc-url LOCAL_RPC --chain-id 31337 --registry-address ACTUAL_REGISTRY --proof-json PUBLIC_PROOF_FILE --pdf ACTUAL_PDF --confirmations 3
```

Use actual results and private local files in place of these placeholders.
The CLI reports institutional current status as NOT_CHECKED; combine it with the
authoritative public lifecycle API. No hash alone establishes present validity.

## Mandatory replacement and security coverage

An authorized real Admin session submits the existing legal-name-change API
with CSRF, expected current reference, approved synthetic registrar evidence and
an idempotency key. The old identity becomes REPLACED immediately. The new
identity receives a separate public reference, frozen name, version, PDF and
commitment. Its issuance depends on confirmed old-key cancellation. The HTTP
suite extracts the new PDF text and checks the corrected names/public identity,
compares preserved credentials, checks Student current/history isolation, and
retains permissioned historical Admin downloads/audit.

The existing database-backed lifecycle tests additionally cover concurrent
matching/conflicting replacements, delayed old workers, preserved skills,
original PDF bytes, and failed PDF/RPC recovery. The existing blockchain tests
cover unauthorized writes/cancellation, invalid issuer/network/contract,
commitment tampering, duplicate anchoring/workers, concurrent nonce reservation,
nonce conflicts, failed transactions, pending confirmations, reorganization,
credential expiry/revocation, invalid receipts and historical verification.

Positive acceptance confirmations are real Anvil evidence. Negative unit tests
inject malformed receipts/timeouts and precise failure boundaries to prove
fail-closed behavior; those are explicitly fault-injection tests, not proof of
successful transactions. Existing crash-boundary tests model lost submission
acknowledgements and restart worker command state from durable database records;
they are not an OS SIGKILL/power-loss durability certification. The HTTP suite
also uses a real disconnected RPC endpoint and restores worker operation while
asserting hashes/nonces are unchanged.

## Optional persistent local environment

The full disposable runner is the recommended repeatable rehearsal. For a
separate operator-managed local website, use the existing
`ANVIL_HANDOFF_2026-10-27.md` deployment/key instructions together with the Phase 1
runtime-pin warning. Use a fresh dedicated database/node for the corrected
registry; preserve all existing demo data and old deployments. Start the node
on loopback, with its state outside Git:

```text
anvil --host 127.0.0.1 --port 8545 --chain-id 31337 --block-time 1 --state PRIVATE_DIRECTORY/state.json --state-interval 1 --silent
```

Generate separate local-only admin/issuer custody; never reuse those keys on
Amoy. Configure `BTU_REGISTRY_ADMIN` and `BTU_REGISTRY_ISSUER`, fund through the
owned loopback Anvil node, and deploy from `blockchain/`:

```text
forge script script/Deploy.s.sol:Deploy --rpc-url http://127.0.0.1:8545 --chain 31337 --unlocked --sender LOCAL_NODE_DEPLOYER_ADDRESS --broadcast
```

Unlocked sending is only for an account actually owned/unlocked by this local
node. Use its actual successful receipt/address, not the evidence file's address.
Keep the matching Django signing file outside Git with restrictive ACLs.
Configure server-only `PASSPORT_BLOCKCHAIN_ENABLED`, `RPC_URL`, `CHAIN_ID`,
`CONTRACT_ADDRESS`, `ISSUER_ADDRESS`, `SIGNING_KEY_FILE`, `CONFIRMATIONS=3` and
`MAX_GAS_PRICE_WEI` using their full `PASSPORT_BLOCKCHAIN_` prefixes. Provision
the existing trusted BTU issuer with an authorized administrator. Use guarded
`config.local_dev_settings` only with the named loopback development database.

Start `run_backend_workers` and `process_blockchain_proofs --watch` separately
with that environment/settings profile. Synthetic records and approvals belong
only in the dedicated local environment; the automatic rehearsal above creates
these without provisioning real university identities or public credentials.
It exercises cancellation/replacement through existing protected endpoints.

Disposable runs automatically stop their owned server/node/cluster and remove
all owned database, mail, media and key files, including on handled failure.
Persistent local services must be stopped explicitly; gracefully interrupt Anvil
so state is saved and stop only the dedicated PostgreSQL cluster. Restart using
its same data/state paths and saved restricted configuration. Never reset a
node beneath an existing database or rewrite immutable saved proof targets.
Clean-state snapshot restart was tested in the earlier handoff; this phase
makes no new power-loss or storage-corruption guarantee.

## Results and readiness

**Phase 2 COMPLETE for disposable Anvil deployment and backend lifecycle acceptance.**
No final test failed or remained blocked. Public Amoy deployment is not performed
or approved by this result, and Phase 3 has not been started.

- Local chain: 31337; required confirmation depth: 3.
- Corrected contract: `0x5B05Cf572Bacaf8dc28bAF9Ef777A65aFe444017`.
- Successful deployment transaction: `0xe58625cc4cef706ced92f6f19d5d211da91d191694993934681886a1675388b9`.
- Deployment block: 1; gas used: 1,169,166.
- Pinned runtime SHA-256: `b087a2e4458e18cb92f52488bc1a22b19490fd101a20d062c581d3a435d16d10`.
- Independent reads: five checks passed, including original/current issuance,
  replacement issuance, historical REPLACED state and final REVOKED state.
- All six tested Student lifecycle operations below reached CONFIRMED.
- The disposable node, database, keys, mail and media have been removed;
  these references cannot be queried on a public explorer or reused as config.

| Operation | Issuer nonce | Actual local transaction | Result |
|---|---:|---|---|
| ISSUE | 1 | `0xb5777f38b5f43a948225eed745345554c5b66a7553882540b842899578c3b14c` | CONFIRMED |
| ISSUE | 2 | `0xa2ccc4e7514fc4e16e7059752ec4b78b5fbac58d0b2a0c24dc9d6be7b10d6d7f` | CONFIRMED |
| ISSUE | 3 | `0x1f382df9ba180d27bb19a2f61eca8fdeebd217e893fa8dd8c3bd9274a55da2be` | CONFIRMED |
| REPLACE | 4 | `0x1edbc71de649307cc39078a88c852a34c1c6021c9e332a77842a8384d7772e3b` | CONFIRMED |
| ISSUE | 5 | `0xc821237580640ab209e1947c56b5ec0014f0f94b241617f599a9348decf45fc4` | CONFIRMED |
| REVOKE | 6 | `0xca3bc4dab378d6c8b95d8d532ff0fc635372be491bea9dda88601b1fa822700f` | CONFIRMED |

| Fresh check | Result |
|---|---|
| Solidity suite | 12 passed, 0 failed, 0 skipped |
| Recompiled pinned artifact | Exact match |
| Five-app PostgreSQL regression suite | All 262 discovered tests passed in 725.163 s |
| Final real HTTP/Anvil acceptance | All 11 journeys passed |
| Independent observer checks | All five passed; no mocked positive confirmations |
| Resource cleanup unit checks | Six passed in 0.155 s |
| Local-profile unit checks | Three passed in 0.007 s |
| Actual PostgreSQL failure/interruption/existing-database safeguards | Passed |
| System checks / migration drift | No issues / no changes detected |
| Whitespace and changed-file syntax/JSON/secret-pattern checks | Passed |

The first enhanced HTTP run also passed. The final run above repeats it after
strengthening preservation assertions to capture credential and achievement IDs
before name correction. Those complete ID sets remain identical afterward.
The scopes of the 262 tests are blockchain, credentials, passports, API and
verification; this is not a new run of every repository application. Coverage
includes parallel signing and replacement races, invalid receipt/commitment,
nonce conflicts, unconfirmed and failed transactions, timeout fault injection,
RPC loss, durable submission recovery, credential revocation and stale workers.
The HTTP run proves live OTP/session/CSRF, Student/Admin authorization, real PDF
integrity, name correction and exact old/new public lifecycle behavior.

Logs: `/tmp/btu-phase2-backend.log`, `/tmp/btu-phase2-http-final.log`,
`/tmp/btu-phase2-foundry.log`, `/tmp/btu-phase2-artifact.log`.
The public evidence JSON contains no private keys, credentials or academic PII.

### Remaining limits and handoff

- No blocker remains for this local acceptance scope. A dedicated approved Amoy
  RPC, issuer/admin custody, sufficient test POL, role/fee/confirmation review
  and explicit public deployment authorization are still required before Amoy
  deployment. Local results do not establish public RPC/consensus availability.
- Automatic fee bump/same-nonce replacement remains outside the existing
  immutable original-byte recovery contract. Preserve Phase 1's operational
  review requirements and old-registry/history transition warning.
- Crash boundary tests model durable submission/restart behavior. An OS-level
  hard kill, power loss or corrupted snapshot is not certified here.
- Frontend visual/browser integration is outside this phase; no design or
  application API contract changed. No shared Neon migration was performed.

Exact changed files: `ops/test_backend_chain_e2e.py` (shared acceptance harness,
blockchain-specific assertions only), `blockchain/PHASE2_LOCAL_EVIDENCE.json`,
`blockchain/PHASE2_REHEARSAL_2026-10-28.md`, `blockchain/README.md`.
No runtime service, schema, migration or production setting changed. Changes
were uncommitted at Phase 2 reporting. The user subsequently authorized committing
and pushing this tested changeset to `feature/passport-blockchain-proof`.
That publication does not authorize a merge, Phase 3 or public deployment.
