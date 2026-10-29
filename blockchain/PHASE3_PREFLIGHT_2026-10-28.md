# Amoy pre-deployment preparation (not deployed; no public broadcast)

## Current submission decision

Following mentor guidance reported by the team on October 28, the submission
will use a video of the locally running Anvil website. Public hosting, additional
POL and public Amoy deployment are not required to record that demo. Follow
[VIDEO_DEMO.md](VIDEO_DEMO.md). This is a scope decision, not deployment evidence:
public Amoy execution remains untested and deferred, with no approved spending.

The reviewed preflight now normalizes Polygon PoA headers before Web3 block
validation and rejects a deployer nonce change during planning. Neither change
adds signing/broadcast capability or changes the Django/contract/API behavior.
Its eight focused tests pass, including an actual disposable Anvil deployment
with chain ID 80002. That node is local, not Polygon Amoy.

The earlier preparation snapshot and user-side RPC readings follow. Its balances
and fee quotes are historical, not current deployment estimates. The table below
distinguishes what this workspace verified from readings supplied by the user.

## Earlier preparation snapshot

Baseline: `dc6da57c9f48a3b72fb4fee8e7e54e306c2686b8`, existing
`feature/passport-blockchain-proof`, initially clean. Contract, artifact and
Django chain/policy adapters are unchanged since Phase 2's passing 262 backend,
12 Solidity and 11 real HTTP/Anvil journeys. No contract recompilation,
branch/worktree switch, merge, commit, push, shared database operation, website
change or public transaction was performed during this preparation.

## Approval report: incomplete; approval is NOT requested yet

| Required item | Verified status |
|---|---|
| Target | Polygon Amoy, chain ID 80002; native currency test POL |
| Deployer and administrator, supplied by user and assigned after delegated role choice | `0x67F16553CF7A0b644143203b04E150219503da05` |
| Issuer, generated privately on the user's computer | `0x1f4A2223539E086f86Afcdc6aC78783B2CB9516d`; user reports restricted folder creation succeeded |
| RPC access | Official HTTPS read failed here; user later successfully queried the PublicNode endpoint below |
| Actual RPC chain ID | User reported 80002; not independently verified here; no fallback |
| Actual wallet balance | User reported deployer/admin 0.01 POL and issuer 0 POL; not independently verified here |
| Actual gas-price quote / public gas estimate | User reported 30 gwei; exact public constructor estimate remains unavailable |
| Secure public-testnet signing custody | Not configured or verified in this workspace |
| Actual Amoy contract / deployment transaction | None; no transaction was sent |
| Deployment spending approval | Not granted; must be requested separately after concrete checks |

The user delegated role selection. The funded MetaMask wallet is selected as deployer/admin; a separate fresh backend issuer avoids placing the admin key in Django. No role assignment is deployed yet. The issuer key must remain in a restricted local file, never this chat. Funding it would be an additional transaction requiring approval.

The failed request used the official public endpoint
`https://rpc-amoy.polygon.technology`, with normal TLS validation and bounded
transport. Its failure establishes no conclusion about the RPC's availability
from the user's computer. No balance, fee, deployment or transaction success is
fabricated. The local Anvil addresses from Phase 2 are not Amoy deployments.

One read-only deployment transaction is to be prepared with value zero, chain
80002, the actually verified deployer nonce, the existing contract creation
bytecode and constructor `(admin, issuer)`. Actual broadcast later is a separate
approved step. The intended post-deployment tests are ISSUE → REPLACE → ISSUE of
the new identity. Those are additional spending actions requiring their own
explicit approval and current estimates; they are not authorized by deployment
approval. A further REVOKE test would require an additional approved transaction.

## Exact tested release

`backend/apps/blockchain/contract.json`: Solidity 0.8.30, Cancun, existing ABI.
Canonical complete JSON SHA-256 (checkout line endings excluded):

```text
91e22e19d6bff82a58456669356b642fcb9adce55493e3ea4f6327c9b57ab167
```

Runtime SHA-256:

```text
b087a2e4458e18cb92f52488bc1a22b19490fd101a20d062c581d3a435d16d10
```

The preflight pins the complete tested artifact and checks its runtime against
Phase 2 evidence. Altering constructor/creation code as well as runtime/ABI
therefore fails closed. It never rebuilds an alternative artifact.

## Prepared read-only tool

`blockchain/scripts/amoy_preflight.py` never loads a private key, signs or
broadcasts; it has no `--broadcast` flag. It:

- Requires an HTTPS `AMOY_RPC_URL` from the process environment; no URL credential
  appears in CLI arguments, report JSON or provider error messages.
- Rejects invalid/zero role addresses, non-EOA deployer/issuer configuration,
  wrong initial chain, pending deployer transactions, invalid fees, changed
  artifact, excessive gas, a changed deployer nonce and a chain change/reorg
  during the reads.
- Applies the same layer-zero PoA header normalization as the runtime Amoy
  adapter. This avoids Web3 rejecting Polygon's oversized `extraData` headers.
- Estimates exact constructor calldata with `eth_estimateGas` as a read-only
  simulation. Gas price is quoted separately and added to the unsigned request;
  the simulation can therefore report a budget even for an unfunded sender.
- Applies a 20% gas-limit buffer and legacy gas-price ceiling, reports actual
  observed balance and whether it covers deployment and a conservative reserve.
- Reports three later operations at the existing 250,000-gas worker limit each,
  clearly as conservative budgeting, not actual future-calldata estimates.
- Produces an unsigned request and public parameters in a new restricted report
  file outside Git, refusing overwrite. Normal stdout excludes bulky calldata.
- Leaves `approval_granted=false`, `transactions_broadcast=0` and
  `signing_custody_verified=false`. A successful read-only report does not prove
  private-key possession or authorize a transaction. Refresh all readings before
  eventual signing; its fee/nonce quote is not a permanent spending grant.

After the RPC is securely configured, run from
the repository root in the installed virtual environment:

```powershell
python blockchain/scripts/amoy_preflight.py --deployer $env:AMOY_DEPLOYER_ADDRESS --admin $env:BTU_REGISTRY_ADMIN --issuer $env:BTU_REGISTRY_ISSUER --output "$env:LOCALAPPDATA\BTU-Passport\issuer\amoy-preflight.json"
```

The external restricted folder must already exist. Keep equivalent user-only
ACLs on Windows. Configure a credential-bearing RPC through a masked local
prompt or private environment file; do not paste it into chat or print the whole
environment. Never reuse the Anvil issuer key or Anvil development mnemonic on
Amoy. Secure deployment signing must use a separately reviewed local MetaMask,
hardware-wallet or encrypted-keystore flow. No public signing method is presently
configured or claimed tested here; do not export a key into chat or CLI args.

Legacy EIP-155 transactions remain intentionally unchanged from the tested
Django adapter and work on an EIP-1559 EVM. The tool does not introduce automatic
fee bumps or same-nonce replacements. Network gas quotes exceeding the configured
ceiling block the plan rather than silently increasing spending.

## POL budget: examples only, not a live estimate

The corrected contract used 1,169,166 gas locally in Phase 2. At a hypothetical
10 gwei, that gas alone costs 0.01169166 POL, before a buffer or Passport tests.
This illustrates why 0.01 POL cannot be assumed sufficient. Actual Amoy fees,
constructor calldata, balance and budget must be measured by preflight. No test
POL transfer or faucet request was made by this phase.

## Initial preparation tests (historical)

```text
python blockchain/scripts/test_amoy_preflight.py
```

All four tests passed in 3.397 seconds. Mainnet, zero roles and changed artifacts
were rejected. The real local test starts its own Anvil with chain ID 80002,
verifies the plan has not advanced nonce/block, checks price and actual zero-
balance handling, then submits the prepared unsigned transaction ONLY to that
owned local node. The real deployment receipt, exact runtime, default admin and
issuer role pass; the node is removed afterward. This local broadcast is not an
Amoy transaction, and no success confirmation is mocked.

Public read attempt: BLOCKED (`RPCUnavailable`); balance/fees remain unverified.
The existing contract/Django runtime did not change, so their Phase 2 results
remain prior evidence; they were not falsely represented as a new full run.

## Video handoff review tests

The same focused command now passes **eight tests**: the original four plus
PoA-header normalization, non-HTTPS rejection, redacted provider exceptions and
safe report paths/no-overwrite. The actual local deployment test also rejects a
nonce that changes during planning. The review does not contact a public RPC or
use a public key for signing. Contract tests and live local website/lifecycle
acceptance are reported in [VIDEO_DEMO.md](VIDEO_DEMO.md#validation).

## Django and client contract after a future authorized deployment

Only actual verified deployment results may configure the existing server-side
`PASSPORT_BLOCKCHAIN_RPC_URL`, `CHAIN_ID=80002`, `CONTRACT_ADDRESS`,
`ISSUER_ADDRESS`, `SIGNING_KEY_FILE`, `CONFIRMATIONS` and `MAX_GAS_PRICE_WEI`
(with the common `PASSPORT_BLOCKCHAIN_` prefix). Enable only with trusted fixed
BTU issuer provisioning and reviewed custodial signing. Existing PostgreSQL
history/immutable targets must not be rewritten to move an old registry.

React, Chrome and future viewers reuse `API_CONTRACT.md`: root current status,
`blockchain_verified`, `historical_blockchain_authentic`, `status`,
`institutional_issuer_approved`, `issuer_key_authorized`, `network`,
`environment`, `chain_id`, `contract_address`, `transaction_hash`,
`required_confirmations`, observed `confirmations`, `onchain_status` and
`transaction_explorer_url`. Only actual Amoy hashes produce fixed
`https://amoy.polygonscan.com/tx/…` links. Pending/unavailable/failed evidence
never establishes current verification; REPLACED/REVOKED overrides historical
integrity. An issued PDF or a saved hash alone is not blockchain verification.
No frontend design or API response schema was changed.

For a future public deployment: obtain working trusted RPC readings and an agreed
secure signing method; produce a complete exact approval report. Only then ask
for deployment approval. Stop without broadcasting until that explicit approval
arrives. Public deployment/lifecycle remains uncompleted and deferred; it is
not a gate for the local video submission.

Role configuration is now concrete: deployer/admin `0x67F16553CF7A0b644143203b04E150219503da05`, issuer `0x1f4A2223539E086f86Afcdc6aC78783B2CB9516d`. The user generated the separate issuer locally and shared its public address only. Its key never entered this workspace/chat. Key-file readability/address match, actual balances, public gas estimate, and signer custody remain unverified here. No funding or deployment approval has been granted.

## User-side RPC update

The user successfully queried `https://polygon-amoy-bor-rpc.publicnode.com` and reported chain ID `0x13882` (80002), deployer balance 0.01 POL, issuer balance 0 POL and suggested gas price 30 gwei. These are user-run RPC readings; this workspace has not independently verified them. At that quote the Phase 2 measured 1,169,166 deployment gas costs 0.03507498 POL before buffer. The buffered 1,403,000-gas illustration costs 0.04209 POL. Three later operations budgeted at 250,000 gas each reserve 0.0225 POL; a simple 21,000-gas funding transfer would cost another 0.00063 POL. Combined illustration: 0.06522 POL, not an exact Amoy calldata estimate or spending approval. Funding/deployment remain unapproved.
