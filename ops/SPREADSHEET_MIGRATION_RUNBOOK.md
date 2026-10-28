# Spreadsheet schema deployment and recovery

This task permits disposable rehearsals only. Do not apply these migrations to
`btu_passport_local`, shared PostgreSQL, staging or Neon without separate explicit
authorization. Existing backend/blockchain migration gates still apply.

`integrations/0003_spreadsheetprofile_spreadsheetpreview_and_more` depends on the
existing integrations/0002, credentials/0005, skills/0003 and swappable account
model. It adds three tables and their protected FKs/constraints. It does not alter
or backfill Student, credential, Passport, version, PDF, issuer, nonce or chain
tables. `integrations/0004_spreadsheet_integrity` adds guards only on those new
tables. No old migration file was edited. Applying forward with no provisioned
profiles does not activate a new source or grant a permission.

The fresh test runner applies the complete schema to a newly owned database.
An additional populated integration/0002 upgrade rehearsal preserves exact rows
for existing identities, linked achievements/credentials, immutable snapshots,
registered PDF bytes/hashes, accounts/grants and genuinely signed/confirmed local
Anvil proof/nonce/observation history. It seeds an existing import run before
the upgrade and verifies that history remains unchanged. These are synthetic
local tests, not a rehearsal of a production-size backup.

For a later approved deployment, pin the reviewed commit and inspect migrate
plans/sql on the exact intended target. Back up and prove restoration of database
and private media. Inventory existing IDs/FKs, snapshot/PDF hashes and chain
operations/nonce counters. Quiesce writes/old import workers as appropriate;
measure PostgreSQL DDL lock/runtime in a restored staging copy. Apply forward
once, compare the inventory, check migration drift and authentication/permission/
import/lifecycle behavior, then provision institution-reviewed profiles disabled
first. Approval, source enablement and real credential ingestion remain separate
operator actions. Never repurpose synthetic test profiles as institutional policy.

Reviewed preview inputs and policy versions cannot be edited/deleted in normal
database writes. Award receipts cannot be rewritten or detached from their domain
records. Actor/domain FKs use PROTECT. Disabling a profile is allowed and prevents
future/retried execution. Confirmation leases are five minutes, renewable per row;
sessions expire after one hour with at most five processing attempts. Lost-process
recovery replays the saved unexpired snapshot after the lease expires. Otherwise
create/review a new preview. The existing domain idempotency receipts prevent
duplicate issuance, including after a crash between row commit and run summary.

Reversing 0004 refuses when any reviewed preview or award history exists. Do not
disable guards or delete history to force a downgrade. A database outage can
prevent receipt/audit persistence; restore service and re-preview the approved
source. Changed source records require institutional resolution and a new reviewed
event where appropriate, never overwriting an existing receipt. Prefer reviewed
forward fixes, with backups and signer operations coordinated by the existing
backend/blockchain runbooks. This implementation performs no chain transaction
replacement, nonce reset, Passport reactivation or historical-artifact rewrite.

Private normalized preview evidence is retained with its audit history. Before
deployment, the institution must approve retention/access/backup rules or a
separately reviewed minimization migration. The implementation does not silently
delete audit evidence or uploaded source data; source files are not stored here.
