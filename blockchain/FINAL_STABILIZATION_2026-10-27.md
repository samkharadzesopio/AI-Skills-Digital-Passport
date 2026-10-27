# Final blockchain stabilization — 27 October 2026

Correction branch: `fix/blockchain-premerge-stabilization`, based on verified Developer 2 source `c8cc9fdd0a8cf07d49c3efa37ff8ac6f482a7f9c`. Website integration remains `cc74833d792f64a9c37764e25cff7108aa524eea`. No branch was merged. No React code, persistent development database, Neon database or public blockchain was modified.

This report supersedes the remaining-code-dependency claims in `STABILIZATION_HANDOFF_2026-10-27.md`. Its earlier failing test evidence remains historical and is not counted as fresh success.

## Corrections and ownership

| Audit item | Result in correction branch |
|---|---|
| Provider selection and Amoy extended headers | Already implemented in c8cc9fd; retained and tested |
| Website-hosted declaration removal | Already implemented; retained. No web/DNS gate was restored |
| Bounded transport and connection cleanup | Already implemented; request-wide middleware registration completed here |
| Private FAILED/NOT_CONFIGURED root mapping | Corrected: only actual PENDING_BLOCKCHAIN becomes pending |
| Required PDF verification regression | Reproduced unchanged at four queries; existing server-only known-document path connected; assertion unchanged |
| Lifecycle/credential terminal precedence | Retained and aligned for private/public on-chain cancellation; current positive verdict additionally requires confirmed live proof and explicit issuer/signer flags |
| Empty snapshot after credential removal | Historical integrity retained, but no current certification badge; empty membership no longer promotes VALID |
| Initial issuance without approved learning evidence | Rejected transactionally; no issued version or publication job created |
| Stuck/dropped transaction handling | c8 diagnostics retained; explicit original-byte operator recovery added |
| Fee/nonce safety | Original signature, payload and current fee cap rechecked; unknown competing pending nonce stops rebroadcast; immutable evidence retained |
| Cross-platform artifact check | Git CRLF normalized in text comparison; complete ABI/creation/runtime comparison retained; contract unchanged |
| Test fixture credentials | Two newly introduced literals replaced with per-run values; no password values published |
| Test isolation | Dedicated fresh-cluster driver added under blockchain/scripts; integration harness unchanged |
| Frontend DTOs, capabilities and current/archive selection | Still owned by later website integration; no React changes made |
| Shared merge conflicts and integration discovery | Still owned by Developer 1 during later authorized integration |
| Migration locking and restricted downgrade | Original protections retained; disposable preservation tests pass. Shared-data sizing, backup and forward recovery remain Developer 1's operational handoff |
| Public Amoy deployment | Not performed; external acceptance remains required |

## Institutional trust and security boundary

Cryptographic proof comes from the expected runtime at the pinned server-configured registry, accepted issuer-role transaction, exact calldata/event/commitment, canonical receipt and required confirmations. Local Anvil evidence is labelled LOCAL_ANVIL.

Institutional approval comes from controlled server deployment configuration and the existing fixed BTU issuer provisioning/verification policy. The database issuer must be trusted and explicitly allowlisted. Requests cannot choose RPC, registry, issuer or network. Configuration is an institutional operator trust root, not a transaction-derived assertion that an arbitrary wallet belongs to BTU. Protect deployment configuration and existing permissioned issuer-provisioning/audit controls. Synthetic tests establish policy behavior, not real BTU approval.

The independent checker has no institution database or signing key. It establishes commitment/chain integrity against the registry the verifier supplies; it reports institutional approval as unknown and does not manufacture current off-chain validity. The institutional API independently evaluates current Passport/credential state.

Students require no wallets. Only test Anvil keys were generated during acceptance. The existing website virtual environment and ignored local configuration were preserved. Admin/deployer/issuer custody and restrictive Windows key-file ACLs remain operator responsibilities. Confirm separate admin and issuer identities/roles before any authorized deployment; do not put the admin/deployer key on the signing worker.

## Operator recovery limits

`inspect_blockchain_operation UUID --check-chain` is read-only. Recovery requires the reviewed saved hash and explicit `--rebroadcast`; it validates the unchanged signature, chain, target, payload, fee and nonce. Operator intent is appended before sending. It does not sign, replace, reset nonce counters, overwrite receipts or discard attempts. Known pool/mined transactions are not rebroadcast. Normal worker rebroadcast and reorganization recovery also validate saved fees and avoid an occupied nonce.

No fee-bump transaction system was added. A temporarily underpriced original can recover when its original fee becomes acceptable; a dropped original can be rebroadcast. An irrecoverably underpriced or externally consumed nonce requires an explicitly reviewed forward recovery design. Never repair it by modifying signed rows or sending unrelated issuer transactions. This is a controlled MVP limitation, not a claim of automatic fee replacement.

## Fresh validation

All results below were freshly executed on this correction. Test counts from different runs overlap and must not be added.

- Initial unchanged regression reproduced: `apps.verification.test_postgres_verification.PostgreSQLVerificationTests.test_real_pdf_uses_existing_repository_and_no_private_response`, four queries versus required three.
- First corrected focused run: 13 passed in 20.787 seconds, including the unchanged regression.
- Foundry: 11 passed, zero failed/skipped. Solidity 0.8.30, Foundry/Anvil 1.7.1, OpenZeppelin 5.4.0.
- Recompiled ABI, creation bytecode and runtime bytecode match the committed artifact. No contract/artifact change.
- Final focused semantics/recovery: 15 passed in 25.624 seconds, including real Anvil underpriced-transaction recovery and fee-cap enforcement.
- Release-focused semantics/recovery: 16 passed in 28.702 seconds, including the added actual on-chain revocation/private-public consistency regression.
- Three corrected fixture regressions: 3 passed in 5.620 seconds.
- Pre-release complete backend run: 550 passed in 462.735 seconds before the final on-chain consistency case.
- **Final release backend run: 551 passed in 525.681 seconds; 553 discovered, the two pre-existing legacy reference-SQL comparisons explicitly excluded. No other skipped/excluded tests reported.** All nine applications, including blockchain, were included on the final runtime/test source.
- Django system check and migration drift: no issues and no changes detected. Git whitespace and changed-Python syntax checks pass. The required `test_postgres_verification.py` test and committed contract artifact are unchanged.

An intermediate full run executed 548 tests in 481.424 seconds and found two failures plus one fixture error. The missing-configuration test still expected the prohibited pending root, the randomized registrar password was not shared with its HTTP login input, and an empty-snapshot fixture lacked approved learning evidence. The first expectation was corrected to the requested UNVERIFIABLE with additional nested/no-positive assertions; login now uses its generated password; the empty-credential fixture now has approved learning and retains its original UNVERIFIABLE assertion. No supported test was removed, and the mandatory three-query regression was not edited. The two additional fee-recovery cases were included in the green 550-test run. Final review added on-chain terminal precedence to the private serializer and its actual Anvil case; the subsequent 551-test run passed.

Executed driver commands used the dedicated Python environment at `C:/Users/User/sth/AI-Passport/.blockchain-stabilization-20261027/venv/Scripts/python.exe`. Logs are retained outside the repository in that task directory: `baseline-query.log`, `focused.log`, `final-focused.log`, `fixture-regressions.log`, `full-backend.log`, `final-full-backend.log`, `release-focused.log` and `release-full-backend.log`. Final verdict: **READY FOR BACKEND INTEGRATION**, meaning the component is locally tested for the subsequent reviewed merge. It does not mean the website integration, staging migration or public Amoy deployment has happened.

Reproduction from repository root, with this branch's requirements installed in an isolated Python environment:

```powershell
python -B blockchain/scripts/test_backend.py
python -B blockchain/scripts/test_backend.py apps.verification.test_postgres_verification.PostgreSQLVerificationTests.test_real_pdf_uses_existing_repository_and_no_private_response
npm.cmd --prefix blockchain ci --ignore-scripts --no-audit --no-fund
npm.cmd --prefix blockchain test
npm.cmd --prefix blockchain run check
```

The Python driver creates a unique temporary PostgreSQL cluster on a dynamically chosen loopback port and random Django test database, resets libpq/blockchain settings, never loads production .env, uses memory mail and temporary media, runs checks/drift/full discovery, then stops/removes only its owned resources. It refuses unsupported labels and preserves its directory if shutdown is unverified. The two pre-existing legacy reference-schema comparisons remain the only explicit runner exclusions. No supported assertion is weakened.

Fresh validation used Windows, Python 3.13, PostgreSQL 18, Web3.py 7.13.0 and Node 26.3.0. All finished driver runs confirmed owned PostgreSQL cleanup. Django routing/session/CSRF tests use its real test client and PostgreSQL; EVM transport/transactions use real local Anvil HTTP. This is not React/Vite/browser acceptance. Forced OS termination cannot guarantee cleanup callbacks; ownership-uncertain resources must be preserved for review.

## API and later integration

Consume `API_CONTRACT.md` and its response examples. Root PENDING_BLOCKCHAIN means genuine pending work. Nested FAILED/NOT_CONFIGURED/UNAVAILABLE becomes root UNVERIFIABLE, subject to terminal lifecycle/credential precedence. Public successful current verification is VALID; private current verification is BLOCKCHAIN_VERIFIED. Historical authenticity, current credential validity and current identity remain independent. An empty current version is not a positive certification verdict.

Preserve the registered request middleware, narrow private serializer mapping and known-document caller change during the later merge. Retain integration's newer disposable launcher and add apps.blockchain to its explicit labels. Resolve route conflicts by keeping both current Admin read endpoints and new registrar/lifecycle routes; preserve session/CSRF and exact grants. Expose new registrar capabilities narrowly when building their future UI. The current React public parser rejects pending/replaced states, private parsers drop proof metadata, and the Admin default must select ACTIVE rather than first UUID. These remain documented integration work, not backend test success.

The combined test command here validates the blockchain branch's existing backend plus corrections. It does not contain the seven newer website integration commits, their React clients or their Student/Admin/public HTTP harnesses. Run that combined acceptance after the separately authorized merge work.

## Database handoff

No correction migration was added. Incorporate accounts 0007, passports 0007/0008 and blockchain 0001/0002. Preserve their dependency order, ACTIVE-only Student uniqueness, frozen names/first issuance, historical ForeignKey relationship, lifecycle permissions/audits, issued-PDF binding, immutable signed evidence and monotonic nonce reservations.

Forward/backward preservation tests run only on disposable PostgreSQL. Existing IDs, snapshot hashes and PDF bytes must survive. Shared deployment needs measured backfill/DDL locks, a backup and stopped old workers. Downgrade intentionally refuses to discard retained proof/lifecycle history; use forward recovery after that boundary. Do not delete/renumber applied migrations.

## Amoy operational checklist — no deployment executed

- Available locally: Solidity source, pinned native Forge/Anvil/compiler, reproducible artifact, PostgreSQL/Anvil acceptance and independent checker.
- Presence-only inspection found no local RPC URL, registry address, issuer address, signing-key path or chain ID in the process/backend environment configuration. No values were printed. No Amoy balance, institutional wallet custody or public transaction was verified.
- Obtain institutional approval for the exact Amoy registry and separate deployer/admin/issuer custody. No real wallet/account is created by this work.
- Configure an approved HTTPS RPC reporting chain 80002; prohibit mainnet and arbitrary request-selected networks.
- Obtain test POL through the authorized process; no account was funded here.
- Simulate deployment, review addresses/roles/runtime, then seek separate explicit broadcast authorization.
- Independently verify canonical deployment receipt, runtime bytecode, default administrator, issuer role and required confirmation depth.
- Provision the fixed trusted BTU issuer and allowlist through the existing controlled process. No university-domain declaration is required.
- Configure protected issuer signing-key storage, exclusive nonce ownership, fee limits and reviewed identity-evidence sources.
- Supervise PDF publication and separate chain/reconciliation workers; monitor stuck transactions, unavailability and retry exhaustion.
- Exercise issuance, immutable version updates, PDF verification, legal replacement, revocation, expiry, outages/restarts and altered bytes on Amoy using independent receipt verification.
- Complete actual website acceptance after integration. Anvil, jsdom or a transaction hash alone cannot establish public-network website completion.

Read deadlines bound transport work, not every possible OS/DNS scheduling delay. Production still needs gateway deadlines, latency monitoring, custody procedures and institution-approved deployment operations.

Protocol references: saved legacy transaction chain binding follows [EIP-155](https://eips.ethereum.org/EIPS/eip-155); the retained layer-zero Polygon header middleware follows [Web3.py 7.13 guidance](https://web3py.readthedocs.io/en/v7.13.0/middleware.html#proof-of-authority). Local tests exercise these behaviors; the references do not establish an Amoy deployment.
