# Local Anvil website video demo

The team reports that its mentor accepts a video of the locally running website
when public blockchain funding is unavailable. The submission path is therefore
React → Django → PostgreSQL → **local Anvil, chain 31337**. It needs no public
website hosting, Amoy funds, wallet extension or external AI API. The local
network still executes actual signed smart-contract transactions.

This changes the submission environment, not the verification rules. Keep
authentication, exact permissions, CSRF, immutable PDFs, three confirmations,
issuer authorization, runtime pinning and independent live chain reads enabled.
Use synthetic university records and explicitly simulated institutional approval.
Do not represent this as real BTU endorsement or public Polygon execution.

## If the saved Anvil state is empty or missing

An empty `state.json` contains no recoverable blockchain history. PostgreSQL
records, PDFs or a deployment receipt cannot recreate that chain's signed
transaction history. Preserve the original database, backups and state file.
Do not bind old proofs to a fresh node or weaken the runtime/receipt checks.

For recording, use the existing disposable acceptance harness's **manual mode**.
It creates a new owned PostgreSQL cluster/database, deploys the current pinned
contract on a fresh Anvil chain, and uses existing domain services to prepare
synthetic credentials, Passport versions, exact PDFs and confirmed commitments.
The website calls the actual Django APIs; sample-data Demo Preview is off.
It does not load your saved `.env`, access Neon, adopt the old database, reuse a
wallet or read/write the old Anvil snapshot. PostgreSQL on port 55433 may remain
running; this session chooses separate loopback ports.

After installing the locked packages described below, run from the repository
root in your Python virtual environment:

```powershell
$env:PASSPORT_PG_BIN = "D:\Program Files\PostgreSQL\bin"
python -u -B ops/run_isolated_tests.py --manual-demo
```

No Playwright installation, faucet, Amoy RPC, private configuration file or
manual migration is required. Migrations apply only to the newly owned empty
database. Setup may take a few minutes. Wait for `LOCAL ANVIL RECORDING READY`
and open the **actual printed Student login URL**; its random port is not 5173
or 5174. The printed public verification URL contains the actual current code.

The launcher prints the path of a private temporary login/OTP JSON file. Open
that file privately in an editor to read `studentEmail` or Admin credentials.
Request the Student OTP through the real login page, then reread `otp` from that
same file. Never paste, record, commit or share its contents. Do not edit the
file. Manual mode uses PBKDF2 password hashing and real OTP/session/CSRF and exact
permissions; the fixture is local-only and not a production configuration.

The console accepts:

| Command | Action |
| --- | --- |
| `status` | Fetch the current public lifecycle/proof verdict through the real API |
| `replace` | Submit the existing authorized name-change API with synthetic registrar evidence; old identity becomes REPLACED and a new identity/PDF/commitment is queued |
| `revoke` | Submit the existing authorized Passport revocation API for the current demo identity |
| `quit` | Stop owned Vite/Django/worker/Anvil/PostgreSQL resources and remove their temporary data |

Background processing calls the existing durable backend and blockchain workers.
Allow their normal retries and at least three real block confirmations. After
`replace`, use `status` and refresh the website until live confirmation succeeds.
No database job/receipt is edited to force green. The registrar/revocation
commands use an actual least-privilege synthetic Admin login, session and CSRF;
they add no application endpoints or registrar UI controls. Only these temporary
fixtures receive the necessary lifecycle capabilities.

This starts with preissued synthetic academic evidence; it is not a recording
of initial Classroom synchronization or live institutional access. The separate
11-journey HTTP driver exercises completion/import-to-credential automation.
Do not present a fixture's prepared credentials as a live Classroom download.

Keep the terminal open throughout one recording session. Use `quit` for a clean
shutdown. A new run creates new identities and transactions; it does not resume
this session. Previously copied/downloaded files and video remain wherever the
operator saved them, but this temporary session's verification URLs stop working
after quitting. Forced power loss/OS kill cannot guarantee cleanup; preserve
unidentified leftovers for review rather than deleting unrelated resources.

Automated rehearsal for this mode (uses its own temporary resources):

```powershell
python -u -B ops/run_isolated_tests.py --demo-smoke
```

It checks real OTP, current PDF/public verification, tampering, denied Student
mutation/missing CSRF, name replacement and confirmed on-chain revocation. This
mode does not require Playwright. The graphical browser check remains separate.

### Fresh recording-mode validation, October 28

- Final `--demo-smoke` passed: actual OTP, original PDF and anonymous verdict,
  tampered-file rejection, denied Student mutation, missing-CSRF denial, legal
  replacement and actual confirmed revocation. Both cancellation receipts were
  independently reread with at least three confirmations. Non-loopback,
  credential-bearing and path-containing console targets were rejected.
- Actual `--manual-demo` launch with terminal input `status` then `quit` passed;
  it reported VALID and removed the owned resources on exit.
- The existing graphical browser regression passed unchanged: five journey
  groups, seven viewport sizes and 94 real API responses, with no interception.
- The selected runs also passed Django checks, migration-drift detection,
  six resource guards, three local-profile tests and the real existing-database
  refusal/cleanup checks. Source syntax, whitespace, links and focused secret
  review passed. No new application model, migration or frontend change.

Review logs: `/tmp/btu-fresh-demo-final-smoke.log`,
`/tmp/btu-fresh-demo-interactive.log`, and
`/tmp/btu-fresh-demo-browser-regression.log`. Sanitized graphical review artifacts:
`/tmp/btu-live-browser-results-01szvhi8`. Owned cluster/private fixture cleanup was
verified after the runs. These Linux cloud results do not certify native Windows
execution, restore the user's lost snapshot, record a video, or establish Amoy
deployment. No full backend regression rerun or persistent database change was
performed. Validation preceded publication; the user subsequently explicitly
approved committing and pushing this tested follow-up to
`feature/passport-blockchain-proof`.

## First check the recording machine

The cloud acceptance environment cannot inspect or change a Windows checkout.
Before updating it, run `git status --short`; preserve any unfinished work. On
`feature/passport-blockchain-proof`, fetch and fast-forward that branch only if
the working tree permits it. Do not merge integration as part of demo preparation.

Install the locked dependencies from the repository root using the intended
virtual environment:

```powershell
python -m pip install -r requirements-blockchain-test.txt
npm.cmd --prefix blockchain ci --ignore-scripts
npm.cmd --prefix frontend ci
npm.cmd --prefix blockchain test
npm.cmd --prefix blockchain run check
```

The contract check compares compiled code with the committed artifact. It does
not inspect an already deployed registry. **The registry previously deployed by
the user before the October 28 zero-replacement fix has the old runtime.** The
current adapter must reject that runtime. Do not disable the pin, edit proof
rows or change an existing document's registry to make it pass. Preserve the old
database, chain state, immutable PDFs and signing history. Use the existing
[registry/migration review](PHASE1_AUDIT_2026-10-28.md) before preparing a fresh
manual deployment. Disposable acceptance below avoids this persistent-data issue.

The user's saved private configuration is outside Git at
`%LOCALAPPDATA%\BTU-Passport\issuer\local-development.env`. Load it privately in
each service process. Do not display its contents or record terminals containing
passwords, wallet output, OTPs or signing keys. Do not copy it into the repository.

With the existing local PostgreSQL cluster and matching Anvil node running, this
read-only check loads that configuration and validates the actual deployment:

```powershell
@'
import os
from pathlib import Path
from dotenv import load_dotenv
import django
import sys

path = Path(os.environ["LOCALAPPDATA"]) / "BTU-Passport/issuer/local-development.env"
if not path.is_file():
    raise SystemExit("Private local configuration not found")
load_dotenv(path, override=True)
sys.path.insert(0, "backend")
os.environ["DJANGO_SETTINGS_MODULE"] = "config.local_dev_settings"
try:
    django.setup()
    from django.core.management import call_command
    from apps.blockchain.chain import configured_gateway
    from apps.blockchain.policy import load_policy, load_signer
    from apps.blockchain.rpc import rpc_budget
    call_command("check")
    call_command("migrate", check=True)
    policy = load_policy()
    if policy is None or policy.chain_id != 31337 or policy.confirmations != 3:
        raise RuntimeError("Expected enabled local Anvil and three confirmations")
    load_signer(policy)  # Checks file permissions/address; never print the key.
    with rpc_budget(25):
        gateway = configured_gateway(policy)
        gateway.signing_context()  # Read-only chain/code/issuer/fee checks.
    print("PASS local Anvil configuration, migrations, pinned runtime and issuer")
except Exception:
    raise SystemExit("Local demo not ready; review configuration, migrations and registry without exposing secrets") from None
'@ | python -
```

This signs/broadcasts nothing and does not apply migrations. A pass does not yet
establish a valid Passport; that requires its actual PDF and confirmed proof.
For pending migrations, follow the backup/restore and separate approval steps in
[the backend runbook](../ops/BACKEND_MIGRATION_RUNBOOK.md) and
[spreadsheet runbook](../ops/SPREADSHEET_MIGRATION_RUNBOOK.md).
The user's spreadsheet backup/restoration was reported successful, but applying
`integrations.0003` and `0004` on that persistent machine is still unconfirmed.
Do not change Neon or reset either PostgreSQL cluster.

## Repeat the isolated acceptance before recording

This command creates and removes its own PostgreSQL cluster, databases, Anvil
deployment, signing material, documents and services. It never adopts the
persistent Windows database or registry. Set the PostgreSQL binary path to the
actual installation; the user's installation is on D:.

```powershell
$env:PASSPORT_PG_BIN = "D:\Program Files\PostgreSQL\bin"
python -B ops/run_isolated_tests.py --chain-http
```

The HTTP driver covers all 11 lifecycle/security journeys, including issuance,
pending confirmation, replacement, revocation, failures and recovery, with
independent chain/PDF checks. It is not a browser recording or a public Amoy test.

Optional actual Chrome acceptance, with Playwright installed outside application
dependencies:

```powershell
$env:BTU_BROWSER_TOOLS = Join-Path $env:LOCALAPPDATA "BTU-Passport\browser-tools"
npm.cmd --prefix "$env:BTU_BROWSER_TOOLS" install --no-save --package-lock=false playwright@1.64.1
& (Join-Path $env:BTU_BROWSER_TOOLS "node_modules\.bin\playwright.cmd") install chromium
python -B ops/run_isolated_tests.py --browser-http
```

`BTU_BROWSER_EXECUTABLE` can select an installed compatible Chromium instead.
The driver uses real API responses and retains only synthetic screenshots and a
sanitized result report. It does not save a video or leave a manual server running.
Stop on any failure. See [the website report](../ops/LOCAL_WEBSITE_ACCEPTANCE_2026-10-28.md)
for the exact previously tested scope; do not call it an Amoy result.

## Start the manual website

After the local checks and separately reviewed database/registry setup pass,
start the existing services using
[the local runbook](../ops/BACKEND_ANVIL_LOCAL_RUNBOOK.md#run-services-together).
Use `VITE_ENABLE_DEMO=false` and the real same-origin Django API proxy. The
frontend's sample-data Demo Mode is not blockchain evidence. Keep PostgreSQL,
Anvil, backend, backend workers, blockchain worker and frontend running together.
Use one coherent database/node/configuration for the entire take.

Open `http://127.0.0.1:5173/student/login`, `/admin/login` and `/verify`.
Use only actual synthetic eligible Student accounts and approved least-privilege
Admin grants. Log in before recording; hide OTP/password entry. No wallet keys
or RPC credentials belong in the browser. The local OTP mailbox is private file
delivery, not a claim of live university email integration.

## Suggested six-minute video

Use the actual IDs/references returned by your run. Do not type example UUIDs or
the words `YOUR_DOCUMENT_REFERENCE` into URLs. Record genuine responses; use cuts
or captions to shorten waits rather than changing states or inserting fake success.

| Sequence | Show and explain | Required observation |
| --- | --- | --- |
| 0:00–0:30 | Website overview and environment | Caption: “Local Anvil · chain 31337 · synthetic BTU records.” Public Amoy is not deployed. |
| 0:30–1:30 | Protected Classroom sync of an approved simulated completion | Existing Student, eligible approved AI course and known mapped skills yield verified achievements and a credential. Replay creates no duplicate credential. Classroom provider is explicitly simulated. |
| 1:30–2:15 | Passport publication and live proof | Let existing workers finish PDF publication and actual chain confirmations. Pending is displayed honestly; show “Blockchain verified · Local Anvil” only after confirmation. |
| 2:15–3:00 | Download exact PDF and anonymously verify it | Original PDF/reference succeeds without login. Show `environment=LOCAL_ANVIL`, `chain_id=31337`, at least three confirmations and no public explorer link. A saved hash alone is insufficient. |
| 3:00–4:15 | Authorized legal-name correction | Use the existing registrar API with `manage_legal_identity`, CSRF, expected current public reference and synthetic approval evidence. Old identity becomes REPLACED immediately; new identity/PDF has a separate confirmed commitment after cancellation confirms. Student, achievements and credentials remain. |
| 4:15–5:00 | Authorized Passport revocation | Use the existing lifecycle API with `manage_passport_lifecycle` and CSRF. Current verification becomes invalid and remains so after the on-chain revocation confirms. Historic cryptographic authenticity is a separate field. |
| 5:00–5:40 | Tampered copy / unavailable proof | A modified PDF cannot inherit the original proof. If demonstrating RPC outage, use a separate synthetic rehearsal: fresh verification becomes unavailable, never stale green. |
| 5:40–6:00 | Repository and deployment status | Show Amoy provider/configuration and read-only preflight, clearly “Amoy deployment pending funding/signing/approval; not executed.” |

The current graphical driver does not click registrar/revocation UI controls.
Those operations are tested through the real HTTP lifecycle driver and existing
authorized API endpoints; no missing UI should be presented as built. The
payloads/permissions are in [API_CONTRACT.md](API_CONTRACT.md#registrar-mutation).
Keep operator approval references private even when synthetic. Preserve a copy
of the original PDF before cancellation to demonstrate its public REPLACED or
REVOKED result afterward. Modify only a copy for the tampering demonstration.

## What Amoy support means here

The code retains the explicit Polygon Amoy provider, chain ID 80002, HTTPS and
PoA-header handling, dedicated signing keys, nonce/retry persistence, fee limits,
confirmation/reorganization checks and fixed Amoy explorer links. The read-only
[preflight](PHASE3_PREFLIGHT_2026-10-28.md) estimates constructor gas and checks
balances without keys or broadcasting. Local chain-80002 tests are compatibility
rehearsals, not proof of transactions on the public network.

No local proof may be relabeled as Amoy. Never change only `chain_id`, invent a
contract/transaction, silently fall back between networks, or reuse Anvil keys
on a public chain. A later real deployment still requires fresh public RPC/gas/
balance/custody checks and separate explicit approval before any spending.

## Submission and remaining limits

Review the final video for keys, seeds, passwords, OTPs, credential-bearing URLs
and actual student data before sharing. Start with a visible local-network
caption and state that institutional approval is simulated. Do not claim live
Classroom/Google Sheets/SMTP access, a Chrome extension, completed Gap Analyzer
UI, hosted deployment or Amoy acceptance from this demo. A recording proves the
recorded local scenario; it does not replace test reports or guarantee production
security. Keep original chain/database/PDF history and private backups outside Git.

## Validation

Prior cloud checks on October 28, 2026, for the original `f70d2cb` handoff
(the recording-mode follow-up results are above):

| Check | Result |
| --- | --- |
| Read-only Amoy preflight suite | 8 tests passed; includes local chain-80002 deployment, PoA headers, nonce-change rejection and redacted errors |
| Solidity registry tests | 12 passed, 0 failed |
| Contract artifact comparison | Foundry source and committed ABI/bytecode match |
| Frontend integration and verification contract scripts | Both passed; synthetic transport fixtures |
| Real HTTP / PostgreSQL / Anvil lifecycle | All 11 journeys passed, with 3 confirmations and independent chain checks |
| Real Chrome → Vite → Django → PostgreSQL / Anvil | 5 journey groups, 7 viewport sizes, 84 actual API responses; no API response interception |
| Owned-resource interruption/cleanup guards | 6 resource tests, 3 local-profile tests and actual existing-database refusal passed; owned services/private data removed |
| Django system checks / migration drift | No issues / no changes detected |
| Python / documented local-check syntax, relative links, whitespace and focused secret-pattern review | Passed |

The graphical run checked the actual Local Anvil badge, current/historical PDF
downloads, anonymous verification, Student/Admin routes, responsive layouts and
logout. Registrar mutation/revocation and outage/recovery remain the separate
HTTP driver's coverage, not additional browser controls. No full nine-app backend
regression rerun is claimed for this documentation/preflight change.

Cloud reproduction:

```text
python -B blockchain/scripts/test_amoy_preflight.py
python -B ops/run_isolated_tests.py --chain-http --browser-http
```

The second command requires the PostgreSQL/Playwright/browser paths described
above. This run used `/tmp/btu-phase1-tools/pg-bin`,
`/tmp/btu-live-browser-tools` and `/usr/bin/chromium`. Its log is
`/tmp/btu-video-demo-acceptance.log`; sanitized synthetic screenshots/results are
in `/tmp/btu-live-browser-results-nkmdn4bv`. These temporary paths are local review
artifacts, not portable deployment configuration or publicly hosted evidence.

No video was recorded by these checks. The Windows commands were syntax-reviewed;
the user's persistent configuration, migrations, old registry transition and
manual recording remain operator tasks. No public RPC, Amoy signing/deployment,
shared Neon migration, hosting, merge or push was performed for this handoff.
