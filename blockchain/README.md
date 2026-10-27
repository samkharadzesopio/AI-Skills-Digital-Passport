# BTU Passport blockchain lifecycle — Anvil MVP

**Anvil (chain 31337) is the primary MVP environment for this handoff.** It uses real local EVM transactions, PostgreSQL persistence and independently checked receipts. No Polygon Amoy deployment, faucet balance or real money is required for integration testing. The Amoy adapter remains available but has not been publicly deployed or validated by this work. Frontend/Chrome browser acceptance and shared database rollout remain separate from backend test results.

Start with [ANVIL_HANDOFF_2026-10-27.md](ANVIL_HANDOFF_2026-10-27.md) for the assigned branch, fresh test results, security review, setup and integration requirements. Earlier reports retain their original Amoy-focused acceptance criteria as historical evidence; the user's current Anvil-first handoff instructions supersede those criteria.

## Architecture

The existing institutional path is retained:

`trusted completion → VerifiedAchievement → Credential → PassportVersion → PassportPublication → stored official PDF → durable blockchain operation → confirmation/reconciliation → public verification`

Every newly published immutable version queues a PostgreSQL `PassportPublication` in its own publication transaction. The publication worker renders outside transactions through the existing document service/template. Issuing a document and enqueuing its chain operation commit together. Existing active versions/documents can be backfilled by the bounded workers without making new versions. No credentials, Student models or PDF persistence services are duplicated.

`apps/blockchain/policy.py` controls Amoy (80002) and local Anvil (31337/1337). Polygon mainnet (137) and all other public chains are rejected. `ChainGateway`, `PolygonAmoyProvider` and `AnvilProvider` separate transport from institutional services. The later addition of a reviewed mainnet deployment policy does not require changing Passport business logic. Mainnet is not enabled here.

`PassportRegistry.sol` uses pinned OpenZeppelin `AccessControlDefaultAdminRules`. Only `ISSUER_ROLE` can issue, cancel for replacement, or revoke. The administrator is a separate role, with a one-day delayed two-step admin transfer. Issuer roles can be granted/revoked on-chain without rewriting historical commitments. No NFTs or student wallets are used.

The registry stores opaque Passport/version/document keys, a salted SHA-256 commitment and the signing issuer. Cancelled keys have terminal REPLACED/REVOKED tombstones. A delayed old issuance cannot reactivate them. Replacement cancellation is confirmed first; the new PDF commitment depends on that operation. All historical commitments/events remain inspectable.

## Legal identity replacement

`apps/passports/lifecycle.py::change_legal_name` requires `accounts.manage_legal_identity`, an approved evidence source, a private registrar evidence reference/reason, an idempotency key and the expected current public Passport reference. Student input or a general admin role is insufficient.

One short transaction locks the Student, checks replay/conflicts, cancels the old identity, updates the approved legal name, creates a new permanent Passport identity, records private immutable approval evidence, queues old-key cancellation and publishes the new snapshot/PDF job. The Student UUID, achievements and legitimate credentials are preserved. Two concurrent approvals against the same expected identity cannot produce conflicting replacements. The old identity is never restored if rendering, RPC or confirmation fails. Missing chain configuration or a quarantined issuer does not undo an approved correction: the immutable lifecycle event retains the pending intent, and the chain worker backfills it when configuration recovers. PDF anchoring ensures the cancellation dependency exists before the replacement can verify.

Current student/dashboard/version/PDF queries filter ACTIVE identities. Students cannot download cancelled identities through historical-version routes. Explicit admin permission and audited existing PDF endpoints retain historical access. Ordinary name edits cannot change the frozen Passport legal-name snapshot or first-issued date. The new identity has its own first-issued date, public ID, version, reference, PDF and commitment.

`revoke_passport` requires `accounts.manage_passport_lifecycle`, immediately hides the identity from current views, records its private approval and queues a terminal on-chain revocation. Normal credential refresh workers resolve only the active identity and cannot resurrect cancellation. Revocation without a replacement requires a later explicit institutional action; it is not silently undone by new credentials.

## Durable signing, failures and recovery

An operation's target, namespace, digest and deployment are immutable. Nonces are reserved under a PostgreSQL row lock per chain/signing address. The fully signed transaction and deterministic hash are saved before broadcasting. RPC calls, file reads and receipt verification take place outside PostgreSQL transactions. Retries reuse the saved transaction; a process crash after sending cannot silently create another issuance.

States: PENDING, SIGNED, SUBMITTED, CONFIRMED, FAILED. Pending confirmations are explicit and never count as verified. Transient RPC/storage/signing-configuration failures have ten bounded exponential-backoff attempts. An operator can requeue transient failures with `--retry-failed`; signed bytes are retained. Reverted transactions and target/key mismatches fail closed for investigation. Fee-bump/replacement transactions are deliberately not guessed automatically. Use a dedicated, exclusively operated issuer signing account; do not consume its nonces with unrelated transactions. For Anvil, fund fresh local-only accounts through its loopback administrative RPC; no faucet is needed. Any later approved Amoy deployment uses separate testnet custody and test POL.

The reconciliation worker checks confirmed receipts against the current canonical chain and keeps separate observations. It can rebroadcast an unchanged transaction lost in a reorganization. Public verification independently rereads the chain each time; the original database CONFIRMED receipt is not accepted as live proof. Provider outages/reorganizations cannot produce a positive result from stale database state.

The Amoy provider injects Polygon PoA header normalization at middleware layer zero. Provider selection validates the complete deployment policy; the independent checker uses the same factory. Verification has a shared six-second RPC budget across replacement dependencies, bounded streaming bodies and no HTTP redirects/retries. `apps.blockchain.middleware.BlockchainRPCBudgetMiddleware` is registered in the integrated production and authentication-test settings and shares that budget across multiple proofs in one HTTP request.

Signing records a SIGNED observation in the existing observation table, in the nonce-reservation transaction. Pending transactions known to the node are not repeatedly broadcast. After fifteen minutes from signing, submissions remain SUBMITTED with `STUCK_TRANSACTION_REVIEW_REQUIRED`; the exact signed bytes and nonce are retained. Legacy signed operations without that observation conservatively use the original operation creation time. Confirmation still recovers automatically if the transaction is mined. If an absent transaction's nonce was consumed elsewhere, the operation fails with `NONCE_CONSUMED_REVIEW_REQUIRED`, retaining all evidence for operator review. A later genuine receipt can still be recovered by reconciliation.

Inspect without reading any signing key or sending any transaction:

```text
python backend/manage.py inspect_blockchain_operation OPERATION_UUID
python backend/manage.py inspect_blockchain_operation OPERATION_UUID --check-chain
```

Check the RPC, signer balance, mempool/receipt, fee conditions and other operations sharing that signer before intervening. Restore connectivity/funding and let the worker retry the original transaction. Never delete signed operations, reset reserved nonces, change immutable signed bytes or make an ad-hoc replacement transaction from the dedicated signer. A fee-bump/cancellation/consumed-nonce repair requires a separately reviewed forward recovery design; it is intentionally not automated by this MVP.

Use an independently supervised signing worker:

```text
python backend/manage.py process_blockchain_proofs --watch --batch-size 20
```

Existing `run_backend_workers` now includes bounded PDF publication after Passport refresh. The chain worker is separate so RPC waits do not block authentication mail. One-shot recovery/inspection:

```text
python backend/manage.py process_passport_publications --batch-size 20
python backend/manage.py process_passport_publications --retry-failed
python backend/manage.py process_blockchain_proofs --batch-size 20
python backend/manage.py process_blockchain_proofs --retry-failed
```

## Privacy and commitment format

No names, email, university Student IDs, raw public UUIDs, grades, achievements or PDF contents are put on-chain. Each Passport gets a random private 32-byte salt. Keys are scoped to chain and registry. A replacement event links two opaque keys; it is still public and potentially linkable if a holder shares proof packets. Hashes are not a promise of anonymity, and blockchain history cannot be erased.

All concatenation below is fixed-width except the specified constant ASCII domain/tag:

```text
N = "BTU_PASSPORT_POLYGON_V1\0" || chain_id_uint256_big_endian || registry_address_20_bytes
P = SHA256(N || "PASSPORT\0" || passport_public_uuid_16_bytes || passport_private_salt_32_bytes)
V = SHA256(N || "VERSION\0" || P || version_public_uuid_16_bytes)
D = SHA256(N || "DOCUMENT\0" || V || document_public_uuid_16_bytes || commitment_salt_32_bytes)
C = SHA256(N || "PDF\0" || P || V || D || pdf_sha256_32_bytes || snapshot_sha256_32_bytes || commitment_salt_32_bytes)
```

The public proof packet contains P/V/D, C, the commitment salt and both hashes for independent recomputation with the uploaded PDF. It never reveals the private Passport salt or former legal name. Each renderer generation has its own document key and proof; an old PDF hash cannot inherit a new PDF's confirmation. The immutable historical PDF bytes are never overwritten.

## Configured issuer trust

The server deployment policy identifies the approved chain, registry and signing address. Verification requires that exact registry's pinned runtime code, an authorized issuance transaction, matching PDF/snapshot commitments, canonical confirmations, the existing trusted fixed BTU database issuer and current Passport/credential validity. Request input cannot select a different deployment or issuer.

No BTU website publication or external identity-declaration request is required. Institutional trust comes from the configured deployment and existing issuer-provisioning controls. The standalone checker reports independently observed chain integrity; the public institutional lifecycle API remains necessary for current off-chain status. Tests use synthetic institutional records and actual local Anvil transactions.

## API and frontend/extension contract

Existing endpoints remain authoritative. See `API_CONTRACT.md` for response rules and examples. The new admin endpoints use existing Django sessions/CSRF and exact capabilities. No wallet keys go to the website or extension.

- POST `/api/admin/students/<Student UUID>/legal-name-change/`
- POST `/api/admin/passports/<internal Passport UUID>/revoke/`
- GET `/api/admin/students/<Student UUID>/passport-lifecycle/`
- GET `/api/verification/blockchain/document/<public document UUID>/`

Existing private current Passport/PDF endpoints now return only the active identity. Existing public Passport/version/PDF-upload verifiers return chain/issuer facts separately from historical authenticity and present-day validity. Registry-only test behavior is confined to the legacy isolated test settings; production sets `PASSPORT_BLOCKCHAIN_ENFORCE=True` unconditionally. Missing chain proof or configured issuer trust must not return VALID or a BLOCKCHAIN_VERIFIED Passport status.

The same nested proof includes `network`, `required_confirmations` and `transaction_explorer_url`. Only Polygon Amoy hashes produce an HTTPS link on the fixed Amoy explorer; Anvil has no public explorer link. A saved transaction link is not a confirmation. Current certification also requires the final registry read to identify the assessed immutable version as latest and VALID, preventing a concurrent version update from retaining a stale current badge.

The frontend/Chrome viewer should display BLOCKCHAIN VERIFIED only when root status is BLOCKCHAIN_VERIFIED and `blockchain.blockchain_verified` is true. REPLACED/REVOKED identities must disappear from current views; clear private queries on identity change/logout and refetch current data, never reuse a cached former Passport. Browser UI integration/deployment acceptance is separate from the backend API tests; no Chrome extension is claimed built by this feature.

## Migration plan for Developer 1 review

No shared Neon migration has been applied.

1. `accounts/0007`: adds explicit registrar and Passport lifecycle capabilities; grants none automatically.
2. `passports/0007`: preserves the Student FK, changes one-to-one to historical one-to-many, adds ACTIVE-only uniqueness, predecessor/lifecycle/first-issuance/frozen-name/salt fields, immutable private lifecycle audit and PDF publication queue.
3. `passports/0008`: backfills each identity from its original issued version without editing any historical version/PDF; gives each Passport an independent salt; guards cancellation/approval/identity immutability in PostgreSQL.
4. `blockchain/0001`: operation queue, signer nonce reservations and chain observations.
5. `blockchain/0002`: immutable target/signed receipt guards, issued-PDF/snapshot binding and monotonic nonces.

Review a staging schema snapshot and migration plan before any shared apply. Back up/measure the one-to-one constraint change and backfill. Application code and migrations must deploy together, with old workers stopped before the relationship changes. Rolling back to the old one-to-one schema is deliberately refused once historical cancelled identities exist. The blockchain migration also refuses to remove its schema while proof receipts exist, before any receipt table can be dropped. Do not discard history to make rollback succeed.

## Local build and tests

See `TEST_REPORT.md` and the current Anvil handoff for the recorded local acceptance scope and exact results. Public-network access is not an acceptance prerequisite for this handoff.

The earlier stabilization history is in `STABILIZATION_HANDOFF_2026-10-27.md` and `FINAL_STABILIZATION_2026-10-27.md`. The integrated baseline and current follow-up are described in `MVP_INTEGRATION_2026-10-27.md`. Complete illustrative response bodies are in `API_EXAMPLES.json`.

Install Python requirements and pinned contract tools:

```text
python -m pip install -r requirements-blockchain-test.txt
npm --prefix blockchain ci
npm --prefix blockchain run build
npm --prefix blockchain test
npm --prefix blockchain run check
```

Foundry 1.7.1, OpenZeppelin 5.4.0 and Solidity 0.8.30/Cancun are pinned. `run check` recompiles with Foundry and compares the committed ABI/creation/runtime bytecode. For a restricted compiler cache, set `SOLC_PATH` to a verified native Solidity 0.8.30 binary. A normal Foundry install can manage the compiler itself. Node wrapper scripts propagate actual native exit codes. Generated artifacts/broadcast/keystore folders are ignored.

Run `python blockchain/scripts/test_backend.py` from repository root. It always initializes a new owned loopback PostgreSQL cluster and random test database, uses generated isolated settings and removes its owned cluster/media on exit. It never imports production settings or adopts a database. Set `PASSPORT_PG_BIN` to installed PostgreSQL binaries when needed. Optional positional test labels select a supported subset; the default includes all nine backend applications, including apps.blockchain. The integrated launcher is `python -B ops/run_isolated_tests.py --backend --chain-http`; it also checks resource cleanup and exercises the real HTTP/session/CSRF/Anvil journeys. Both paths automatically start and stop their own local Anvil instances with fresh local-only signing material.

On Windows use `npm.cmd ci --ignore-scripts` in blockchain: the pinned generic Foundry package postinstall uses POSIX environment-assignment syntax. Platform-native optional binaries are already locked; the project wrappers invoke those binaries directly. `npm.cmd test` and `npm.cmd run check` exercise the same pinned tools. Artifact checks normalize Git checkout line endings while retaining the complete ABI/bytecode comparison.

## Manual local Django and Anvil

For a development viewer, use the existing guarded database/mail configuration in `ops/LOCAL_DEVELOPMENT.md`. Keep it separate from the disposable automated tests above. Start a loopback-only node with a standard Foundry installation (or invoke the pinned platform-native Anvil executable under `blockchain/node_modules/@foundry-rs/`):

```text
anvil --host 127.0.0.1 --port 8545 --chain-id 31337 --block-time 1 --silent
```

Anvil accounts and funds are local test material; never reuse those keys on Amoy. Choose local-only admin, issuer and deployer accounts/keystores, and fund the latter two on this Anvil instance. With their public `BTU_REGISTRY_ADMIN` and `BTU_REGISTRY_ISSUER` environment values set, run from `blockchain/`:

```text
forge script script/Deploy.s.sol:Deploy --rpc-url http://127.0.0.1:8545 --chain 31337 --account LOCAL_ONLY_DEPLOYER --broadcast
```

That command broadcasts only to the explicit loopback node. Use its actual deployed address, never a documentation example. Configure `PASSPORT_BLOCKCHAIN_ENABLED=true`, `PASSPORT_BLOCKCHAIN_CHAIN_ID=31337`, `PASSPORT_BLOCKCHAIN_RPC_URL=http://127.0.0.1:8545`, the local contract/issuer addresses, a restricted local issuer key file, and the existing trusted fixed BTU issuer/allowlist. The one-second block interval allows the default three-confirmation policy to progress even without other transactions. Automated tests also exercise one-confirmation and explicitly pending three-confirmation scenarios. A restarted empty Anvil chain requires a new local deployment; saved database receipts cannot establish proof on an empty chain. Keep Anvil on the Django host's loopback interface; its administrative RPC must not be exposed publicly.

With the reviewed **local** migrations already applied through the existing local-development workflow, start these in separate terminals from repository root:

```text
python backend/manage.py runserver 127.0.0.1:8000 --settings=config.local_dev_settings
python backend/manage.py run_backend_workers --settings=config.local_dev_settings
python backend/manage.py process_blockchain_proofs --watch --settings=config.local_dev_settings
```

The guarded local profile requires `BTU_LOCAL_DEVELOPMENT=1`, `DJANGO_DEBUG=true`, a loopback `btu_passport_local` database and the existing explicit account policy. These commands do not apply migrations or provision issuers. Test the existing authenticated Student/PDF APIs and anonymous verification APIs from `API_CONTRACT.md`. Local evidence reports `network: Anvil`, `environment: LOCAL_ANVIL` and no public explorer URL. Frontend parser/display acceptance remains necessary; running a Django server does not complete the website integration.

The chain tests start their own Anvil subprocess with an ephemeral mnemonic generated at runtime, deploy the actual contract, send real signed local transactions and exercise Django/PostgreSQL/PDF/public endpoints. They do not use eth-tester or a database-only EVM simulator. `PASSPORT_ANVIL_BIN` can select an installed native binary. No public wallet or RPC credentials are needed for local tests.

## Controlled transaction recovery

Inspect one operation first, using `inspect_blockchain_operation OPERATION_UUID --check-chain`. A stuck transaction is not verified. After reviewing its saved hash and chain state, an operator can run:

```text
python backend/manage.py recover_blockchain_operation OPERATION_UUID --expected-transaction-hash REVIEWED_HASH --rebroadcast
```

This command uses no signing key. It validates the original signature, chain, target, calldata, gas, fee cap and reserved nonce; it persists operator intent before rebroadcasting exactly the saved bytes. Already known/mined transactions are not broadcast again. A nonce consumed or occupied by another transaction, terminal failure, changed bytes, or cancelled identity stops recovery. Crash/retry uses the same hash and nonce. Historical signed evidence and frozen receipts are retained.

No automatic or manual fee increase is implemented. A temporarily underpriced transaction must wait until its original fee is acceptable, then the dropped original may be rebroadcast. If that cannot resolve an incident, a reviewed forward transaction-attempt design is required. Do not reset nonces, edit signed rows, send unrelated transactions from the issuer, or discard history. This explicit limitation is preferable to an untested replacement mechanism. Public-network recovery is an operator action requiring its normal authorization; this stabilization executed local Anvil transactions only.

## Optional later Polygon Amoy deployment: prepared, not executed

This section is retained for a separately approved public-testnet deployment. It is **not required for the current Anvil MVP handoff**.

Required external inputs: explicit authorization, an approved administrator/issuer key policy, an Amoy RPC endpoint, a deployer funded with test POL and a separately controlled issuer funded for its transactions. Students never need wallets. No mainnet deployment is permitted.

Use a standard Foundry installation and encrypted deployer keystore (`cast wallet import NAME --interactive`). Set public addresses `BTU_REGISTRY_ADMIN` and `BTU_REGISTRY_ISSUER`; keep the administrator key off the Django signing worker. Simulate and review first:

```text
forge script script/Deploy.s.sol:Deploy --rpc-url AMOY_RPC --chain 80002 --account APPROVED_DEPLOYER
```

Run from `blockchain/`. The script rejects every chain except Amoy/local Anvil. **Do not add `--broadcast` until the exact deployment is reviewed and explicitly authorized.** Once authorized, the same command with `--broadcast` submits real testnet transactions. Record and independently check the receipt's status, canonical block, deployed code hash, default administrator and ISSUER_ROLE. Pending output is not deployment success.

After deployment, configure the server securely:

```dotenv
PASSPORT_BLOCKCHAIN_ENABLED=true
PASSPORT_BLOCKCHAIN_CHAIN_ID=80002
PASSPORT_BLOCKCHAIN_RPC_URL=APPROVED_HTTPS_AMOY_RPC
PASSPORT_BLOCKCHAIN_CONTRACT_ADDRESS=ACTUAL_DEPLOYED_REGISTRY
PASSPORT_BLOCKCHAIN_ISSUER_ADDRESS=APPROVED_ISSUER_ADDRESS
PASSPORT_BLOCKCHAIN_SIGNING_KEY_FILE=RESTRICTED_FILE_OUTSIDE_REPOSITORY
PASSPORT_BLOCKCHAIN_CONFIRMATIONS=3
PASSPORT_BLOCKCHAIN_MAX_GAS_PRICE_WEI=50000000000
PASSPORT_IDENTITY_EVIDENCE_SOURCES=BTU_REGISTRAR
```

Provision the fixed BTU database issuer through the existing authorized service. Use TLS/private storage, restrictive Unix key-file mode 0600 or equivalent Windows ACLs, supervised workers and a dedicated issuer account. The RPC endpoint must report 80002; do not use an Anvil result as evidence of Amoy success. Keep old signing keys authorized until their queued work is safely drained or explicitly resolved. Retain historic deployment artifacts and trust records when planning future deployments; this MVP currently permits one reviewed registry deployment per environment.

If a later public Amoy release is requested, its acceptance must reproduce: approved completion → PDF → confirmed proof → anonymous upload/reference check; legal replacement → old REPLACED + new independent proof; revocation; failed RPC/restart recovery; changed bytes; unauthorized key; current/historical distinction. Confirm receipt and events via an independent Amoy RPC or explorer, and test the real website/extension consumers. Until then, label that public-network deployment untested; it does not block the present Anvil integration handoff.
