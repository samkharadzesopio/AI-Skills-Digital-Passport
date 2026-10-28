# Anvil MVP integration handoff — 27 October 2026

## Scope and branch

Assigned branch: `feature/passport-blockchain-proof`. Finalization starts from
`c87f801c2ffee350c93b90551e3d4fbbf5c73622`; use the final published Git commit
for this handoff. The branch was clean at inspection. Its former head `c8cc9fd`
was an ancestor of the completed `feature/blockchain-mvp-completion` work, so it
was fast-forwarded without a new merge commit or rewriting history. The latter
branch and all other branches/worktrees are preserved. Integration's already
completed backend/frontend commits are retained as existing history; no React
page was independently edited in this finalization.

The user has designated **Anvil as the primary MVP environment**. Polygon Amoy
funding/deployment is not required for this handoff. Earlier reports' public
Amoy acceptance requirements are historical and superseded for this scope.
The Amoy adapter remains implemented, but no public deployment or public
transaction success is claimed. Anvil evidence must always be labelled local.

## Completed implementation retained

1. Trusted completion → existing verified achievements → existing Credential
   service → immutable Passport version → durable PDF publication → actual
   signed EVM transaction → confirmation → existing public verification.
2. Solidity registry with authorized issuer operations, immutable document
   commitments, duplicate rejection, terminal replacement/revocation tombstones,
   issuer rotation and delayed two-step default-administrator rotation.
3. Domain-separated salted Passport/version/document/PDF commitments. No Student
   names, email, grades, raw public UUIDs or PDF bytes are published on-chain.
   Students do not require wallets.
4. PostgreSQL operation persistence, immutable signed bytes/hash/nonce/targets,
   locked monotonic nonce reservations, concurrent duplicate protection,
   sign-before-broadcast durability and exact-byte retry after uncertain sends.
5. Pending confirmations, bounded retry/backoff, outages/timeouts, stuck and
   competing nonce diagnostics, worker restart recovery, reconciliation after
   reorganization, read-only inspection and reviewed original-byte rebroadcast.
6. Live independent validation of chain ID, pinned runtime code, transaction
   hash/signer/nonce/calldata/value, event, commitment, canonical block and
   confirmation depth. A saved database CONFIRMED flag alone never verifies.
7. Approved legal-name replacement: exact registrar capability, expected current
   identity, trusted evidence source, immutable approval audit, immediate old
   identity cancellation, distinct new identity/version/PDF and a separate
   commitment dependent on confirmed cancellation. Student ownership, skills,
   credentials and historical PDF bytes remain intact.
8. Permissioned Passport revocation and current credential revocation/expiry
   checks. Authentic history never overrides present invalidity. Empty refreshed
   snapshots cannot restore a certification badge.
9. Existing Student/dashboard/PDF/public reference/version/upload APIs carry the
   same proof facts. Private current-only ownership, session/CSRF, admin history
   permissions/audit, public upload limits, throttling and no-store are retained.
10. Truthful pending/unavailable/failed/not-configured/terminal states; separate
    current validity and historical authenticity. Fixed network metadata and
    safe Amoy-only explorer links; Anvil has no public explorer link.
11. The final institutional registry assessment must still identify the version
    as VALID and latest. A concurrent new version cannot leave the old proof's
    current-verification flag true.
12. Fixed trusted BTU issuer provisioning and server allowlist, restricted signing
    files, explicit Anvil/Amoy provider selection, mainnet rejection, Amoy header
    compatibility and shared request RPC budgets. No university website gate.
13. Independent PDF/transaction checker using the same contract and commitment
    rules, without a signing key or institutional database. It does not invent
    current institutional validity from chain integrity alone.

No duplicate Student, issuer, credential, Passport or verification service was
introduced. No new model or migration is needed by this finalization.

## Fresh validation

Results are filled from the completed runs, not inferred from earlier reports.

| Check | Result |
| --- | --- |
| Foundry contract tests | 11 passed; 0 failed; 0 skipped |
| Rebuilt ABI/creation/runtime artifact | Exact match |
| Actual Forge `Deploy.s.sol` broadcast to owned Anvil | Passed; receipt status 1, pinned runtime and admin/issuer roles verified |
| Nine-application PostgreSQL regression | 563 ran in 1238.650 s: 562 passed, 1 setup error; 565 discovered, only the 2 existing legacy reference-SQL comparisons excluded |
| Focused lifecycle/privacy rerun | All 23 passed in 117.149 s, including the previously blocked privacy test; the same connection timeouts and assertions were retained |
| Real HTTP/session/CSRF/Anvil lifecycle acceptance | All 11 journeys passed in the separate runner; owned database/media/mail/server/signer/cluster cleanup verified; exit 0 |
| System checks / migration drift | No issues / no changes detected |
| Owned test-resource unit and PostgreSQL disposal checks | Passed; 6 resource tests and 3 local-policy tests |
| Anvil persistence/interval-mining probe | Passed; independently verified actual issuance with at least 3 confirmations before state load, after CLI state load, and after graceful CLI restart; one-second mining advanced blocks |
| Documented issuer-file example | Passed; only the public address printed, file mode 0600, accepted by the existing signer loader, existing file preserved, checkout location rejected, owned key directory removed |

The broad run's single error was
`apps.blockchain.test_lifecycle.PassportReplacementTests.test_chain_calldata_contains_only_opaque_keys_not_personal_identifiers`.
Its fixture could not establish the loopback PostgreSQL connection within the
existing five-second limit while creating its Student. The test body did not
run; no privacy assertion failed. This is recorded as an error, not a pass.
The complete lifecycle module subsequently passed on a fresh owned cluster.
No timeout, assertion or test-selection exclusion was changed to hide the error;
the broad run remains recorded as failed.

The runner uses a newly initialized, exclusively owned PostgreSQL 17 cluster on
a dynamic loopback port, temporary databases/media and fresh local-only Anvil
signing material. It does not load production `.env`, adopt old databases or
modify Neon. Test-cluster fsync/synchronous commit/full-page writes are disabled
for speed; these runs do not establish power-loss durability. Native Foundry/
Anvil 1.7.1, Solidity 0.8.30, OpenZeppelin 5.4.0, Python 3.13 and web3.py 7.13.0
are used. The two pre-existing legacy reference-SQL comparisons remain the
runner's only exclusions; no assertion is relaxed.

Canonical reproduction from the repository root:

```text
python -m pip install -r requirements-blockchain-test.txt
npm --prefix blockchain ci --ignore-scripts --no-audit --no-fund
npm --prefix blockchain test
npm --prefix blockchain run check
python -B ops/run_isolated_tests.py --backend --chain-http
```

Set `PASSPORT_PG_BIN` to installed PostgreSQL binaries. On Windows use `npm.cmd`.
This cloud run selects the installed compiler with `SOLC_PATH=/tmp/btu-solc-0.8.30`
and uses `/tmp/btu-mvp-pg-bin` wrappers for the extracted PostgreSQL installation.
An external `/tmp/btu-anvil-handoff-run.py` only streams the backend test output;
test selection, assertions and resource cleanup remain the existing runner's.
The separate HTTP run used `/tmp/btu-anvil-handoff-http-run.py` solely to stream
its output; its selection and assertions were unchanged. The focused rerun was
`python -B blockchain/scripts/test_backend.py apps.blockchain.test_lifecycle`.
Logs are `/tmp/btu-anvil-handoff-{backend,lifecycle-rerun,http,foundry,artifact,
state-check,deploy-check,forge-deploy}.log`. Persistence and Forge deployment probes used
separate owned temporary nodes/directories and no public RPC. They validate
clean local restart/deployment, not power-loss or public-network behavior.

## Security review

A redacted pattern scan of all history reachable from `c87f801` examined 728
blobs (715 text blobs) and the 446 tracked paths. No private-key block/literal,
literal seed phrase, common GitHub/AWS/Google/Slack token pattern, or tracked
private environment/key file was found. Environment examples contain placeholders,
not credentials. Review also confirms runtime-generated test keys, server-only
signing, no key material in the response contract, exact permissions/CSRF and
fail-closed issuer/chain verification. Pattern scans have limits and are not an
independent security certification. Final staged paths are reviewed before push.

Inherited repository history contains development-marked Django signing keys and
synthetic application-password fixtures, already investigated in
`ops/SECURITY_CREDENTIAL_INVESTIGATION.md`. Current deployment settings require
environment-provided keys; current affected fixtures generate fresh credentials.
No new live credential is introduced by this handoff. Historical reuse in a live
environment remains unverified: its owner must rotate any reused key/password
and invalidate affected sessions. Preserving existing Git history does not
erase that earlier exposure; no history rewrite or production rotation is
performed here.

Only example `.env.example` files belong in Git. Keep `.env`, raw signing keys,
encrypted keystores, passwords and Anvil state/backups outside the checkout.
Never put them in shell arguments, source, browser bundles or chat. Apply Unix
mode 0600 to the issuer file and restrictive parent-directory permissions; on
Windows apply the equivalent user-only ACL. Use fresh local-only keys for Anvil.

Anvil permits administrative state changes and impersonation. Bind it to
loopback on the Django host; do not expose its RPC through the website or to the
public internet. This local test chain is not decentralized public consensus.

## Anvil startup and deployment

Automated tests need only the pinned npm tools and create/deploy their own owned
Anvil nodes. For a persistent local website environment, use a standard Foundry
installation including `anvil`, `forge` and `cast`.

Create a private directory outside the checkout. In the commands below,
`ANVIL_PRIVATE_DIRECTORY`, `DEPLOYER_KEYSTORE`, `DEPLOYER_ADDRESS`,
`ISSUER_ADDRESS`, `REGISTRY_ADDRESS` and `DEPLOYMENT_TX` are placeholders for
your own local paths and actual public results, not supplied wallets or hashes.
Create a local encrypted deployer keystore with:

```text
cast wallet new ANVIL_PRIVATE_DIRECTORY/deployer
```

Use the resulting keystore path for `DEPLOYER_KEYSTORE`; obtain its public
address with `cast wallet address --keystore DEPLOYER_KEYSTORE`. Use a separately
generated local issuer key in a restricted file outside Git, and its matching
public `ISSUER_ADDRESS`. The Django worker expects a raw hex private-key file;
an encrypted keystore JSON is not its signing-file format. Keep the administrator
and issuer separate. No actual private key is included in these instructions.

To generate the local issuer without printing its key, set the environment
variable `BTU_ANVIL_PRIVATE_DIRECTORY` to that external private directory and run
the following Python from the repository root in the installed virtual
environment. It refuses to overwrite an existing issuer file. On Windows apply
the directory/file's user-only ACL before using it.

```python
import os
from pathlib import Path
from eth_account import Account

repository = Path.cwd().resolve()
directory = Path(os.environ['BTU_ANVIL_PRIVATE_DIRECTORY']).expanduser().resolve()
if directory == repository or repository in directory.parents:
    raise ValueError('Keep local keys outside the checkout.')
directory.mkdir(parents=True, exist_ok=True, mode=0o700)
issuer = Account.create()
descriptor = os.open(directory / 'issuer.key', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, 'w', encoding='ascii') as stream:
    stream.write(issuer.key.hex())
print('ISSUER_ADDRESS=' + issuer.address)
```

Start Anvil in its own terminal; replace the directory placeholder first:

```text
anvil --host 127.0.0.1 --port 8545 --chain-id 31337 --block-time 1 --state ANVIL_PRIVATE_DIRECTORY/state.json --state-interval 1 --silent
```

The one-second blocks allow three-confirmation issuance to progress without
other transactions. The state path must remain the same when restarting the
same local environment. Never reset the chain underneath an existing database
and treat its old saved receipts as current evidence.

Fund the fresh local deployer and issuer through the **loopback Anvil RPC**.
These commands set ten local native tokens per address and consume no faucet
tokens, money or issuer signing nonces:

```text
cast rpc --rpc-url http://127.0.0.1:8545 anvil_setBalance DEPLOYER_ADDRESS 0x8ac7230489e80000
cast rpc --rpc-url http://127.0.0.1:8545 anvil_setBalance ISSUER_ADDRESS 0x8ac7230489e80000
```

Set public environment variables `BTU_REGISTRY_ADMIN=DEPLOYER_ADDRESS` and
`BTU_REGISTRY_ISSUER=ISSUER_ADDRESS`. From `blockchain/`, deploy:

```text
forge script script/Deploy.s.sol:Deploy --rpc-url http://127.0.0.1:8545 --chain 31337 --keystore DEPLOYER_KEYSTORE --broadcast
```

Enter the keystore password interactively. Record the actual registry address
and transaction, then inspect:

```text
cast receipt DEPLOYMENT_TX --rpc-url http://127.0.0.1:8545
cast code REGISTRY_ADDRESS --rpc-url http://127.0.0.1:8545
cast call REGISTRY_ADDRESS "defaultAdmin()(address)" --rpc-url http://127.0.0.1:8545
```

The actual service validates the pinned runtime and issuer role before spending
gas. The keystore-based manual CLI workflow is operator setup guidance. This
handoff also actually tested the following **local Anvil-only** Forge command,
using a deployer listed by the local node's `eth_accounts`:

```text
forge script script/Deploy.s.sol:Deploy --rpc-url http://127.0.0.1:8545 --chain 31337 --unlocked --sender ANVIL_UNLOCKED_DEPLOYER_ADDRESS --broadcast
```

The CLI test checked its real receipt, exact runtime and role assignments.
Unlocked signing is for the owned loopback Anvil node only; it is not a public
deployment method. The encrypted-keystore/password flow was not executed in
this workspace. The automated suite additionally deploys through real
Anvil/Web3 and checks unauthorized-operation rejection.

## Django integration requirements

Use `ops/LOCAL_DEVELOPMENT.md` for the guarded local PostgreSQL/mailbox profile.
It requires `BTU_LOCAL_DEVELOPMENT=1`, `DJANGO_DEBUG=true`, explicit account policy
and the loopback database `btu_passport_local`. Keep database credentials and
generated Django/auth secrets in the ignored local environment, not examples.
On another deployment profile, preserve the existing authentication/TLS policy.

Set these server-only values using actual local deployment results:

```dotenv
PASSPORT_BLOCKCHAIN_ENABLED=true
PASSPORT_BLOCKCHAIN_RPC_URL=http://127.0.0.1:8545
PASSPORT_BLOCKCHAIN_CHAIN_ID=31337
PASSPORT_BLOCKCHAIN_CONTRACT_ADDRESS=REGISTRY_ADDRESS
PASSPORT_BLOCKCHAIN_ISSUER_ADDRESS=ISSUER_ADDRESS
PASSPORT_BLOCKCHAIN_SIGNING_KEY_FILE=ABSOLUTE_RESTRICTED_ISSUER_FILE_OUTSIDE_GIT
PASSPORT_BLOCKCHAIN_CONFIRMATIONS=3
PASSPORT_BLOCKCHAIN_MAX_GAS_PRICE_WEI=50000000000
VERIFICATION_TRUSTED_ISSUER_REFERENCES=BTU-UNIVERSITY
BTU_CLASSROOM_ISSUER_REFERENCE=BTU-UNIVERSITY
PASSPORT_IDENTITY_EVIDENCE_SOURCES=BTU_REGISTRAR
```

BTU_REGISTRAR is the synthetic local approval source for a controlled demo;
deployment operators must configure their approved evidence policy. The issuer
record must already be provisioned by the existing service for an authorized
admin; it is never implicitly created by blockchain code. Where needed, the
existing local-only provisioning command is:

```text
python backend/manage.py provision_btu_issuer --actor-email AUTHORIZED_LOCAL_ADMIN_EMAIL --settings=config.local_dev_settings
```

Review and apply the existing local migration plan before starting services.
Required blockchain/lifecycle migrations are accounts `0007_alter_user_options`,
passports `0007_passportlifecycleevent_passportpublication_and_more` and
`0008_lifecycle_integrity`, blockchain `0001_initial` and `0002_proof_integrity`.
No new migration is added here. See `ops/BACKEND_MIGRATION_RUNBOOK.md` for schema
preservation, backups, lock/backfill review and restricted downgrade. Shared
Neon migrations are outside this task and are not run automatically.

Start these processes separately from the repository root:

```text
python backend/manage.py check --settings=config.local_dev_settings
python backend/manage.py runserver 127.0.0.1:8000 --settings=config.local_dev_settings
python backend/manage.py run_backend_workers --settings=config.local_dev_settings
python backend/manage.py process_blockchain_proofs --watch --settings=config.local_dev_settings
```

Keep the registered request RPC-budget middleware, private root status mapping,
known-issued-document upload hint and `apps.blockchain` test discovery. Never
wrap blockchain I/O in `ATOMIC_REQUESTS` or explicit PostgreSQL transactions.
Do not run competing applications or unrelated transactions from the issuer.

Clients use the existing endpoints and original PDF template in `API_CONTRACT.md`.
Authenticated Student/PDF reads stay self-scoped. Registrar mutations require
their exact capabilities and CSRF. Public proofs contain no signing files, RPC
credentials or private Student/source payloads. Save an actual proof and PDF to
verify independently without a database/key:

```text
python blockchain/scripts/verify_transaction.py --rpc-url http://127.0.0.1:8545 --chain-id 31337 --registry-address REGISTRY_ADDRESS --proof-json actual-proof.json --pdf actual-passport.pdf --confirmations 3
```

Keep those generated files private/outside Git. The checker establishes the
actual commitment and canonical chain evidence; the existing public BTU API
also checks current institutional lifecycle and credential validity.

## Outstanding work and limits

- No public Amoy deployment/acceptance was performed or required. Anvil results
  must not be presented as public Polygon transactions.
- The earlier combined run returned one dashboard HTTP 500, then two HTTP runs
  passed. Its cause was not identified. The current rerun includes sanitized
  failure-location capture and passed all 11 journeys without reproducing it;
  any recurrence must be investigated, not ignored.
- This finalization's broad run had one five-second local PostgreSQL connection
  timeout during privacy-test setup. The unchanged complete lifecycle module
  passed all 23 tests on a fresh cluster, and separate HTTP acceptance passed.
  The original broad run is still **not fully green**. Recheck host/database
  capacity and rerun combined CI during integration; no timeout was increased
  or error hidden to obtain a passing label.
- There is no automatic fee bump or nonce reassignment. Reviewed recovery can
  rebroadcast only the original bytes; irrecoverably underpriced or consumed
  nonces require a forward repair design. Signed evidence is never edited.
- Existing React DTO parsers/Passport views and the Chrome/Classroom viewer need
  the integration owner's implementation/acceptance. Preserve the local network label, pending
  and failure states, active-identity selection and cache invalidation. Backend
  HTTP success is not browser acceptance. No frontend redesign is included.
  The exact existing consumer changes are listed in `ops/BACKEND_API_HANDOFF.md`:
  Student/PDF and public-verification DTOs must retain proof facts, the auth
  capability allowlist must retain registrar/lifecycle grants, and Admin history
  must default to the ACTIVE identity. No Chrome extension implementation or
  browser acceptance is claimed by this branch.
- A clean Anvil state restore is distinct from power-loss/corrupted-state
  recovery. Keep consistent PostgreSQL/media/node/key backups and protect its
  administrative RPC. Never delete audit or nonce history to obtain a badge.

## Readiness and publication

**READY FOR ANVIL BACKEND INTEGRATION TESTING, with the reported test-environment
timeout and inherited security caveats.** Every retained blockchain feature
listed above has passing relevant tests, including the previously blocked
privacy test in its focused rerun. This does not convert the broad run's error
into a pass, establish a completely green combined CI run, or claim completed
frontend/Chrome acceptance. No Amoy deployment is a prerequisite.

The finalization changes documentation/API guidance and `.env.example` comments
only; it retains the already implemented and committed runtime fixes through
`c87f801`. The authorized commit and normal fast-forward push target only
`feature/passport-blockchain-proof`. No integration/main merge, history rewrite,
public transaction or shared-data migration is included.
