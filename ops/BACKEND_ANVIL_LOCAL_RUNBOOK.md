# Backend and Anvil local MVP startup

This is an operator handoff, not permission to migrate an existing database.
This candidate was validated only against new owned PostgreSQL clusters and
temporary Anvil chains. No persistent local/Neon database or existing server was
modified. Public Amoy is optional and is not required for this MVP.

For the current mentor-approved video submission, follow
[the video checklist](../blockchain/VIDEO_DEMO.md). Current graphical website
acceptance is recorded in [the October 28 report](LOCAL_WEBSITE_ACCEPTANCE_2026-10-28.md).

## Reproduce safe automated acceptance

From this candidate's repository root, use an existing compatible Python 3.13
environment containing the pinned `requirements.txt` dependencies. On Windows:

```powershell
npm.cmd --prefix blockchain ci --ignore-scripts --no-audit --no-fund
npm.cmd --prefix frontend ci --ignore-scripts --no-audit --no-fund
npm.cmd --prefix blockchain test
npm.cmd --prefix blockchain run check
python -B ops/run_isolated_tests.py --full
```

Select the intended virtual environment's `python.exe` explicitly if it is not
activated. `PASSPORT_PG_BIN` can identify PostgreSQL 18 binaries;
`PASSPORT_ANVIL_BIN` and `PASSPORT_FORGE_BIN` can identify the pinned native
executables. `SOLC_PATH` can select verified Solidity 0.8.30. Windows Foundry npm
postinstall uses POSIX assignment syntax, so install with `--ignore-scripts`;
the repository wrappers select the locked native optional binaries.

The launcher creates a fresh cluster on a random loopback port, unique
`test_owned_...` databases, ephemeral signer material, mail, media and Vite
caches. It rejects existing databases and libpq redirection, never imports
production `.env`, and shuts down only its own resources. Never replace it with
a shared-database connection. `--backend --chain-http` runs backend/Anvil tests
without the legacy React drivers. All processes stop when the tests finish.

## Prepare a manual local demo separately

Use a reviewed checkout and one coherent local database/Anvil deployment. The
existing `config.local_dev_settings` deliberately permits only loopback
`btu_passport_local`, explicit development activation and DEBUG. It is not a
generic temporary-database profile. Do not point it at Neon or use test settings
for a persistent database.

The persistent local database was not inspected or upgraded by this task. Before
using this newer schema there, follow [the migration runbook](BACKEND_MIGRATION_RUNBOOK.md):
verify backup/restoration, review actual migration leaves/SQL, stop old writers
and workers, inventory IDs/snapshots/PDF hashes/grants, and approve the forward
plan. Do not let old and new lifecycle schemas serve concurrently.

With operator-provided local configuration, the read-only planning commands are:

```powershell
python backend/manage.py check --settings=config.local_dev_settings
python backend/manage.py showmigrations --plan --settings=config.local_dev_settings
python backend/manage.py migrate --plan --settings=config.local_dev_settings
```

Only after that separate backup/review/approval, the forward apply command is:

```powershell
python backend/manage.py migrate --noinput --settings=config.local_dev_settings
python backend/manage.py migrate --check --settings=config.local_dev_settings
```

Do not edit applied migrations, reset schemas/nonces, delete old identities or
rewrite issued documents. No new migration is introduced by this candidate.

Required configuration **names** (provide secrets privately; no values belong in Git):

| Purpose | Environment names |
| --- | --- |
| Guarded local profile and database | `BTU_LOCAL_DEVELOPMENT`, `DJANGO_DEBUG`, `DATABASE_URL` |
| Independent authentication secrets | `DJANGO_SECRET_KEY`, `AUTH_TOKEN_PEPPER`, `ACCOUNTS_OTP_HMAC_KEY` |
| Eligible Student statuses and mail | `ACCOUNTS_ACTIVE_STUDENT_STATUSES`, `DJANGO_DEFAULT_FROM_EMAIL`; the local profile uses a private file mailbox |
| Institutional issuer and sources | `BTU_CLASSROOM_ISSUER_REFERENCE`, `VERIFICATION_TRUSTED_ISSUER_REFERENCES`, `BTU_AUTHORIZED_COMPLETION_SOURCES`, `PASSPORT_IDENTITY_EVIDENCE_SOURCES` |
| Blockchain target | `PASSPORT_BLOCKCHAIN_ENABLED`, `PASSPORT_BLOCKCHAIN_RPC_URL`, `PASSPORT_BLOCKCHAIN_CHAIN_ID`, `PASSPORT_BLOCKCHAIN_CONTRACT_ADDRESS`, `PASSPORT_BLOCKCHAIN_ISSUER_ADDRESS` |
| Signing and confirmation policy | `PASSPORT_BLOCKCHAIN_SIGNING_KEY_FILE`, `PASSPORT_BLOCKCHAIN_CONFIRMATIONS`, `PASSPORT_BLOCKCHAIN_MAX_GAS_PRICE_WEI` |
| Optional approved Sheets source | `BTU_GOOGLE_SHEET_ID`, `GOOGLE_SERVICE_ACCOUNT_FILE` |
| Vite live development | `VITE_ENABLE_DEMO`, `BTU_DEV_API_TARGET` |

Keep `.env`, mailboxes, database backups and signer files outside Git. Restrict
the signer file to its operator (Windows ACLs must be set by the operator;
POSIX mode is checked). Use fresh local-only keys. Never reuse a developer or
public-network key, and never display an Anvil mnemonic/private key in logs.

## Start Anvil and deploy the pinned registry

With installed Foundry or the pinned native binaries:

```text
anvil --host 127.0.0.1 --port 8545 --chain-id 31337 --block-time 1 --silent
```

This manual command uses Anvil's public development accounts; use them only on
the loopback test chain. Automated tests instead generate fresh mnemonic/key
material at runtime. Choose local-only admin, issuer and deployer accounts,
fund the latter two on this Anvil chain, and set the public address variables
`BTU_REGISTRY_ADMIN` and `BTU_REGISTRY_ISSUER`. From `blockchain/`, deploy with a
password-protected local-only Foundry deployer keystore:

```text
forge script script/Deploy.s.sol:Deploy --rpc-url http://127.0.0.1:8545 --chain 31337 --account LOCAL_ONLY_DEPLOYER --broadcast
```

Copy the actual deployed public contract address into the local target
configuration; use chain ID 31337 and the loopback RPC above. The issuer key
file must correspond to the explicitly authorized issuer. The gateway checks
chain ID, exact pinned runtime bytecode, issuer role, fees and every signed
transaction. It cannot silently select a different network. Retain three required
confirmations for the local demo, as used by current acceptance; the one-second
block interval lets confirmations advance without another transaction. Observed
confirmations remain live facts. No Amoy deployment/RPC/wallet is needed.

Existing document targets and signed bytes are immutable. A reset/empty Anvil
chain or a new contract address does not rebind old database records. Preserve
the matching local chain state, or prepare a separate reviewed demo environment;
never "repair" the mismatch by editing proof rows or deleting history.

## Run services together

After the separately approved migration/configuration steps, keep these running
in separate terminals from the same checkout and local environment:

```text
python backend/manage.py runserver 127.0.0.1:8000 --noreload --settings=config.local_dev_settings
python backend/manage.py run_backend_workers --settings=config.local_dev_settings
python backend/manage.py process_blockchain_proofs --watch --settings=config.local_dev_settings
npm.cmd --prefix frontend run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

PostgreSQL and Anvil must remain running too. The shared worker delivers queued
auth mail, retries integrations, refreshes credential/expiration snapshots,
publishes PDFs and cleans bounded expired state. It never ingests simulated
Classroom automatically. The separate signer worker drains/recovers proof jobs
and rechecks confirmations; operate the issuer exclusively. For one bounded
cycle, use `run_backend_workers --once` or `process_blockchain_proofs` without
`--watch`. Neither starts Anvil nor deploys a registry.

Keep Demo Mode off. Vite proxies `/api` to loopback Django, preserving Host and
Origin for cookies/CSRF. `BTU_DEV_API_TARGET` selects another trusted local API
port. Production static hosting needs its own same-origin HTTPS gateway.
`ops/start_local.ps1` can start Django/Vite and refuses pending migrations or
occupied ports; it does not start Anvil, provision accounts/issuer or run workers.

## Accounts, trusted evidence and verification

Student OTP requires an eligible canonical Student with the approved university
email/status. Login creates no academic evidence or Passport. In the local
profile, read only the intended synthetic mailbox file privately; do not print
OTP values. Production requires approved TLS SMTP and worker operation.

Use only synthetic local accounts. `bootstrap_admin --help` describes the
interactive password prompt and explicit grants; it refuses a second initial
administrator. Existing operators must use the established account-management
process. Never grant superuser or all permissions to get a screen working.
`provision_btu_issuer --actor-email SYNTHETIC_APPROVED_ADMIN` provisions the fixed
issuer only for an explicitly authorized administrator. Do not auto-provision
institutional trust from uploaded evidence or arbitrary UI input.

Current grants are `view_student_records`, `manage_student_accounts`,
`manage_credentials`, `revoke_credentials`, `sync_classroom`,
`import_completions`, `manage_legal_identity`, `manage_passport_lifecycle`.
Grant only the actions assigned to each operator. Migrations grant none.

Use approved synthetic strict completion columns from the API handoff; verify
bad/pending/rejected evidence issues nothing. Classroom remains simulated.
Google Sheets requires a server-approved source/service account and was not
exercised live. Flexible profile/preview integration is now present; its additive
migrations require [their own review and backup procedure](SPREADSHEET_MIGRATION_RUNBOOK.md).

Open `/student/login`, `/admin/login` or `/verify` under the Vite origin. The
backend routes are in [the API handoff](BACKEND_API_HANDOFF.md). CSRF GET returns
200; anonymous `/api/accounts/me/` returns 403; a bare Django `/` returning 404
is normal. Mutations require actual session cookies and refreshed CSRF tokens.
Download the exact registered PDF, then submit it anonymously. Current success
requires the fresh root verdict and nested proof flags; a hash/transaction link,
ISSUED document or old CONFIRMED database row alone is insufficient.

The current React parsers include blockchain/lifecycle integration. Real graphical
Chrome acceptance against Django and Anvil passed in the separate October 28
report linked above. This does not establish the state of any persistent Windows
setup, a hosted website, or public Amoy. Repeat disposable acceptance using the
safe automated command at the top; the focused graphical command is in the video
checklist.

## Troubleshooting

| Symptom | Check and safe response |
| --- | --- |
| Authentication unavailable | Check the actual failed status; explicit Student status policy, PostgreSQL, mail configuration and correct settings/worktree. Do not relax OTP/CSRF. |
| Anonymous `/me/` 403 | Expected signed-out state; use real login. |
| Local SSL error | Select the guarded local profile only for its named loopback database; keep production TLS. |
| Pending migrations | Stop launch, review backup/plan; never auto-migrate a persistent database. |
| PENDING_BLOCKCHAIN | Inspect publication/signing jobs, signer worker, Anvil and confirmation depth; pending is never verified. |
| UNVERIFIABLE / NOT_CONFIGURED | Check all target settings and fixed issuer approval; preserve fail-closed behavior. |
| UNAVAILABLE / RPC_TIMEOUT | Restore the same deployment; saved confirmations are not live proof. |
| Wrong chain/runtime/issuer | Correct operator configuration after review; never change pinned bytecode/trust checks. |
| Stuck nonce/fee failure | Inspect the operation and original transaction; do not reset/re-sign. Follow reviewed original-byte recovery in the migration runbook. |
| Replaced/revoked Student content 404 | Expected cancellation boundary; authorized Admin history remains available. |
| Missing Google configuration | Configure an approved source privately, or demonstrate labelled synthetic fixtures. |
| Unexpected dashboard 500 | Capture sanitized exception type and stack locations from the HTTP driver; investigate the actual recurrence. No historical root cause is assumed. |
