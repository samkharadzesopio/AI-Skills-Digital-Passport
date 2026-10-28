# Google Sheets: local preparation and approved live acceptance

## Status and boundaries

The starting integration commit is `6ddd218c1bd1cc94853f59feafa723fb23aae72e`.
The existing importer already supplied approved sources, immutable mapping
profiles, private administrator previews, source/digest confirmation, record
receipts, audit/history and the shared credential/Passport publication pipeline.
No frontend or authentication change is needed. Sopio can keep the current API:

- `GET /api/integrations/import/profiles/`
- `POST /api/integrations/import/google-sheets/preview/` with only `profile_id`
- `GET /api/integrations/import/previews/{id}/`
- `POST /api/integrations/import/previews/{id}/confirm/` with
  `{"confirm":true,"snapshot_sha256":"<reviewed digest>"}`

The current authorization is **local synthetic preparation only**. Do not access
Google, use real credentials, create cloud resources, or run the live commands
below until the owner separately approves them. Local passing tests use a
provider fixture, real loopback HTTP, owned PostgreSQL and disposable Anvil.
They do not establish Google authentication, sharing, quotas or live acceptance.

## Manual setup, after institutional approval

1. **Create a test Google Cloud project.** Sign into the approved institutional
   account at <https://console.cloud.google.com/>. Open the project selector,
   choose **New project**, enter a name such as `BTU Passport Sheets Test`, select
   the approved organization/location, and create it. Select the new project.
   Project creation and key creation may require an institutional administrator.

2. **Enable Google Sheets API.** In **APIs & Services → Library**, search for
   **Google Sheets API**, open it and select **Enable**. This adapter opens files
   by exact ID and needs no Google Drive API or Drive scope. See Google's
   [API enablement guide](https://developers.google.com/workspace/guides/enable-apis).

3. **Create a dedicated service account.** In **IAM & Admin → Service Accounts**,
   select **Create service account**. Use a dedicated name such as
   `btu-passport-sheets-test-reader`. Create it; leave optional project roles and
   user-access grants empty. Do not grant Owner, Editor or domain-wide
   delegation. Record its service-account email. The account's read-only access
   comes from the Sheet's Viewer sharing role plus the application's sole OAuth
   scope `https://www.googleapis.com/auth/spreadsheets.readonly`.
   See [service-account creation](https://docs.cloud.google.com/iam/docs/service-accounts-create)
   and [Sheets scopes](https://developers.google.com/workspace/sheets/api/scopes).

4. **Create a fictional Google spreadsheet.** With your institutional Google
   account, create a new blank spreadsheet named `BTU Synthetic Passport Test`.
   Do not copy real student records. Rename its first worksheet exactly
   `Passport Skill Records`. Put `Synthetic workbook` in A1, leave rows 2–3
   empty, and paste this tab-separated block starting at A4:

   ```text
   Institutional Approval	Skill ID	Student ID	Date Earned	Record ID	Ignored note
   CONFIRMED	SYNTHETIC-SKILL	SYNTHETIC-STUDENT	2026-01-01	SYNTHETIC-RECORD	synthetic
   CONFIRMED	SYNTHETIC-SKILL	SYNTHETIC-STUDENT	2026-01-01	SYNTHETIC-RECORD	synthetic
   PENDING	SYNTHETIC-SKILL	SYNTHETIC-STUDENT	2026-01-01	SYNTHETIC-PENDING	synthetic
   CONFIRMED	SYNTHETIC-SKILL		2026-01-01	SYNTHETIC-MISSING	synthetic
   CONFIRMED	SYNTHETIC-UNAPPROVED	SYNTHETIC-STUDENT	2026-01-01	SYNTHETIC-BAD-SKILL	synthetic
   CONFIRMED	SYNTHETIC-SKILL	'=1+1	2026-01-01	SYNTHETIC-FORMULA	synthetic
   ```

   The apostrophe in the last Student ID makes Google store the literal `=1+1`
   rather than calculate it; the importer must reject this evidence. Format the
   Date Earned cells as plain text containing `2026-01-01`. The expected preview
   has header row 4, **1 valid, 1 duplicate, 1 review, 3 invalid**. The template is
   checked exactly before the acceptance runner imports anything. Leave the
   remainder of A1:F20 empty. The ignored note column is intentionally unmapped.

5. **Share privately with the service account.** Open **Share**, add its exact
   email from step 3, select **Viewer**, and save. Keep General access
   **Restricted**. If institutional external-sharing policy blocks that address,
   ask the administrator to approve this dedicated account; do not make the file
   public or enable delegation. Service accounts need explicit sharing, as
   described in [gspread authentication](https://docs.gspread.org/en/v6.2.1/oauth2.html).
   Create a second, separate empty synthetic spreadsheet for the missing-access
   test, leave it Restricted, and **do not share it** with the service account.
   Its owner must approve a read attempt to that exact negative-test ID too.

6. **Record the IDs and range.** In
   `https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit#gid=0`, copy only
   the text between `/d/` and `/edit` as the spreadsheet ID. The `gid` is not the
   spreadsheet ID or worksheet name. Record both test spreadsheet IDs, the
   exact worksheet tab name `Passport Skill Records`, and approved range
   `A1:F20`. The application permits bounded A1 ranges beginning at A1, up to
   A1:Z5011, so preview row numbers retain their original meaning.

7. **Create and store the JSON key outside Git.** First create a private local
   folder such as `C:\Users\User\.btu-passport-secrets`, outside this workspace
   and every Git checkout. Restrict its Windows ACL to the operator/runtime
   identity and institutionally required administrators. In **IAM & Admin →
   Service Accounts → the dedicated account → Keys → Add key → Create new key**,
   choose **JSON**. Save/move the downloaded file to that private folder as
   `google-sheets-test.json`; inspect and restrict the file's ACL as well. Keep
   no copy in Downloads, repositories, frontend assets, chat or logs. Never paste
   the JSON/private key. If key creation is blocked by organization policy, ask
   the administrator for an approved solution; do not disable policy.
   Google documents these steps and key-handling constraints in
   [Create service account keys](https://docs.cloud.google.com/iam/docs/keys-create-delete).
   This adapter currently accepts a service-account JSON file; keyless workload
   identity would require a separate implementation and approval.

Return only non-secret configuration details: project ID, service-account email,
absolute JSON **path**, both synthetic spreadsheet IDs, worksheet, range and
institutional approval reference. Explicitly approve read-only Google access
to those IDs when ready. Do not send tokens or key contents.

For a **new** private Windows folder, the operator can use this PowerShell
recipe before downloading the key (retain additional IT-managed access if your
institution requires it):

```powershell
$secretDir = Join-Path $env:USERPROFILE '.btu-passport-secrets'
$operatorIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
New-Item -ItemType Directory -Path $secretDir -Force | Out-Null
icacls $secretDir /inheritance:r /grant:r "${operatorIdentity}:(OI)(CI)F"
```

After saving/moving the JSON there, restrict and inspect the file too:

```powershell
$secretPath = Join-Path $secretDir 'google-sheets-test.json'
icacls $secretPath /inheritance:r /grant:r "${operatorIdentity}:F"
icacls $secretPath
```

The ACL output should contain only approved operator/runtime and IT principals.
Do not display the JSON contents. These commands are manual future setup, not
actions performed by the local acceptance run.

## Future live acceptance, only after that separate approval

Create a small operator configuration file **outside Git**, for example
`C:\Users\User\.btu-passport-secrets\google-acceptance.json`:

```json
{
  "target": {
    "spreadsheet_id": "REPLACE_APPROVED_SPREADSHEET_ID",
    "worksheet": "Passport Skill Records",
    "range": "A1:F20"
  },
  "unshared_spreadsheet_id": "REPLACE_APPROVED_NEGATIVE_TEST_ID",
  "credential_file": "C:\\Users\\User\\.btu-passport-secrets\\google-sheets-test.json",
  "approval_reference": "REPLACE_WITH_INSTITUTIONAL_SYNTHETIC_TEST_APPROVAL"
}
```

Use the project Python environment with `backend/requirements.txt` installed;
PostgreSQL binaries and the pinned native Anvil binary must be available. In an
interactive PowerShell terminal at the feature worktree root:

```powershell
$env:PASSPORT_ANVIL_BIN = 'C:\path\to\anvil.exe'
python -B ops/run_isolated_tests.py --google-sheet-live 'C:\Users\User\.btu-passport-secrets\google-acceptance.json' --allow-google-read
```

This command creates and disposes its own loopback PostgreSQL cluster, media,
accounts, HTTP server and Anvil; it never loads `.env` or adopts a database. The
credential can only read Google. At the prompt, **you**, as Sheet owner, change
F5 from `synthetic` to `synthetic changed`, then press Enter. Do not change
anything else. This proves that even an ignored cell change within the approved
range invalidates the reviewed source snapshot. A new preview is then reviewed
and confirmed through the same session/CSRF APIs. Restore F5 manually before
another run. Allow up to 15 minutes; interrupting unwinds owned resources.

Passing live acceptance requires real Google authentication, exact target read,
unshared access denial, unconfigured-target denial, row decisions, no issuance
before confirmation, digest rejection, changed-source rejection, confirmation,
replay, PostgreSQL achievement, Student Passport/PDF, three-confirmation Anvil
publication, independent RPC/receipt/commitment reads, anonymous verification,
and modified-PDF rejection. A partial run is not full live acceptance. No
acceptance result from a provider fixture counts as Google API evidence.

## Backend configuration for an approved deployment

Only after an operator has reviewed the environment and institutional policy:

- Set `GOOGLE_SERVICE_ACCOUNT_FILE` to the absolute private key path outside Git.
  The flexible reader rejects relative paths, missing files and Git-contained
  files (including worktrees). The legacy strict importer is retained unchanged;
  deployment preflight also checks the external credential location.
- Add `BTU_GOOGLE_SHEETS` to the authorized completion-source policy; retain other
  approved sources as needed. Authorization is not enabled by adding a target.
- Configure the existing fixed issuer, trust allowlist and eligible Student
  statuses. Do not create or trust an institutional issuer implicitly.
- Set `BTU_SPREADSHEET_GOOGLE_SOURCES_JSON` server-side to, for example,
  `{"approved":{"spreadsheet_id":"REPLACE_APPROVED_SPREADSHEET_ID","worksheet":"Passport Skill Records","range":"A1:F20"}}`.
  Existing two-field targets retain the old bounded `A1:Z5011` range. The target
  and optional range are bound into the preview's source digest; changing them
  requires a new review. No target, range or credential is supplied by React.
- Provision an institutionally reviewed immutable profile using
  `python backend/manage.py provision_spreadsheet_profile --manifest <reviewed.json> --enable`.
  The example `ops/examples/google-sheets-profile.synthetic.json` is **only** for
  synthetic acceptance, not an institutional approval or real catalog policy.
  The real Student and Skill catalogs must already exist and be authorized.
- `python backend/manage.py deployment_preflight` checks configuration/schema
  without Google requests, migrations, issuer provisioning or mail. A flexible
  target no longer requires the unrelated legacy `BTU_GOOGLE_SHEET_ID` setting.
- After separate external-access approval, an optional read-only diagnostic is
  `python backend/manage.py check_google_sheet --profile-id <uuid> --approval-reference <exact-profile-reference> --allow-google-read`.
  It checks policy, reads and maps the source, prints counts/digest only, and
  never creates previews, achievements or credentials. Its PASS means read/map
  success, not that every mapped row is eligible or the issuance chain passed.

No new migrations are required. Never apply migrations or change shared/staging
configuration as part of this local preparation. Keep keys out of all `VITE_*`
variables, bundles, reports and commits. Rotate/revoke keys through the approved
operator process after testing or compromise.

## Security and operating limits

The only OAuth scope is Sheets read-only; no Drive scope, listing, write calls,
domain-wide delegation or public sharing is used. **Google's scope and Viewer
ACL cover the whole spreadsheet, not one tab or range.** The worksheet/range
allowlist is application policy, not a Google range-level authorization boundary.
Use a dedicated file containing only approved data; never put unrelated private
records on another tab of the same shared file.

The reader uses connect/read timeouts `(5, 10)` seconds, three attempts only for
transient reads (429/5xx/transport failures), exponential delay with jitter, and
no import/confirmation retry. Authorization/configuration failures are not
retried. Sessions created for a read are closed. These are bounded attempts and
per-request timeouts, not an end-to-end wall-clock deadline. Multiple Sheets
metadata/value calls and OAuth refresh can occur in one attempt. Respect the
[current Google quotas](https://developers.google.com/workspace/sheets/api/limits)
and limit operator concurrency; persistent 429s fail safely and need operator
review. Do not broaden permissions as an error workaround.

Raw Google errors and credential/source contents are excluded from API errors.
Admin session, capability, CSRF, private-preview ownership and no-store rules
are unchanged. Only an explicitly confirmed reviewed snapshot issues eligible
records; PENDING/REJECTED rows and mapped formulas cannot issue. Duplicate
receipts preserve replay safety. Excel and all response formats remain intact.

## Local-only regression command and frontend handoff

```powershell
python -B ops/run_isolated_tests.py --backend --spreadsheet --google-sheet --chain-http
```

`--google-sheet` always uses the labeled synthetic provider; `--full` and other
ordinary regression flags cannot select live Google. Both explicit live flags
are required for the future live runner. Focused regressions cover target/range
validation, credential placement, timeout/retry/error handling, approval guards,
preflight and the existing spreadsheet/migration/permission cases.

Sopio needs no React change: source IDs/ranges/keys stay server-side; profiles
appear through the existing list. Continue displaying the existing safe Google
unavailable, changed-source and reviewed-digest errors. Review API compatibility
with Sopio's latest branch before merging this feature. The feature branch can
be pushed normally; neither integration nor frontend branches are merged here.
