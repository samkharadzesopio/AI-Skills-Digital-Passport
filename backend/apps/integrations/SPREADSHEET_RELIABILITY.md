# Phase E: authorized imports, durable history and replay

Excel and Google Sheets default production processing now reuses the existing
completion inbox and credential automation. It no longer reports an achievement
as a credential. No Student, Skill, issuer, credential or Passport models/services
were duplicated or changed. The legacy injected award_func remains only as an
explicit unit-test seam; API production paths use persistent processing.

## Institutional authorization and configuration

Besides the existing active, verified administrator's explicit
`accounts.import_completions` permission, each source must be approved in the
Django setting BTU_AUTHORIZED_COMPLETION_SOURCES (list/tuple). Default is no
spreadsheet issuance. Allowed values are BTU_EXCEL and BTU_GOOGLE_SHEETS. Approval
means the institution authorizes these controlled import channels as evidence;
permission to upload arbitrary files alone is NOT approval of their contents.
Require approved record provenance, administrator training and source governance.

Shared-settings bindings to coordinate (not changed here):

```python
BTU_AUTHORIZED_COMPLETION_SOURCES = [
    v.strip() for v in os.environ.get('BTU_AUTHORIZED_COMPLETION_SOURCES', '').split(',') if v.strip()
]
BTU_GOOGLE_SHEET_ID = os.environ.get('BTU_GOOGLE_SHEET_ID', '')
GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get('GOOGLE_SERVICE_ACCOUNT_FILE', '')
```

Google ID is read only from server settings, never the request. Give the service
account read-only access only to the institutional spreadsheet. Provision its file
securely; never commit credentials. gspread==6.2.1 is now declared in requirements.
The read uses a fixed Completions worksheet, A1:Z5002 range and 10-second request
timeout. Live Google service access/credentials were not available or tested.
Excel requires .xlsx and is limited to 5 MiB compressed, 32 MiB ZIP expansion,
1,000 archive members, 26 columns, 5,000 data rows and 16 KiB textual content per
row. Request parsing installs bounded upload handling before session CSRF can
parse multipart data. Gateway total body/field/time limits from Phase C still apply.

All completions still require an existing external Student ID, completed/passed
status, finite passing grade, valid nonfuture date, and exact approved catalog/skill
mapping. The approved issuer is the fixed `BTU-UNIVERSITY` reference used by the
shared completion service. Its trusted record must already be provisioned by an
authorized administrator; imports cannot choose or provision an issuer.
No caller-supplied issuer/source/mapping can grant an award. Numeric grades in
spreadsheet receipts are canonicalized to float to prevent 90 versus 90.0 conflicts.

## Persistence and recovery

`integrations/0002_importrun_and_more` depends on integrations/0001,
credentials/0004, skills/0002 and the swappable user initial migration. It adds
ImportRun with actor, timestamps, summary, sanitized invalid-row classifications
and many-to-many event references. It expands the existing inbox source constraint
to the two explicitly controlled spreadsheet sources; all unique receipt and
retry constraints are preserved. No migrations were applied to shared Neon.

An ImportRun is created before parsing/fetching. Accepted rows are registered and
linked before processing, then reuse the same staged achievement/credential
transactions, stable namespaced keys, five-attempt budget and conflict detection
as Classroom. An existing achievement is replayed even if earlier credential
issuance failed. Issuance and completion status commit together. Concurrent
imports/repeated uploads create one credential per source-event identity.

Source namespaces are deliberately distinct. An institutional completion exported
under different source identities is not silently treated as the same event.
Developer 1/institution must agree on canonical cross-source event IDs/aliases if
exports are intended to describe the same completion; do not guess equivalence
from Student/course alone.

- GET `/api/integrations/imports/`: cursor-paginated import history (50/page).
- POST `/api/integrations/imports/events/<inbox UUID>/retry/`: authorized replay of
  the saved spreadsheet event; no replacement payload. Requires import permission.
- Classroom history/retry endpoints remain limited to Classroom events and sync
  permission. An import-only administrator cannot retry Classroom events.
- Existing `retry_classroom_events` operator command now processes due events
  across the supported completion inbox sources; no second retry engine exists.
- `reconcile_import_runs` refreshes current event counts for partial/failed runs
  and interrupted RUNNING runs older than five minutes. It does not refetch sources.
  Interrupted fetches with no receipt are marked for operator re-import. Schedule
  reconciliation and retry polling through a trusted operator environment.

Original summaries describe that import attempt. Reconciliation adds current_issued,
current_failed and current_pending counts; it does not rewrite historical attempt
counts or pretend invalid rows succeeded. Parser-invalid rows are stored as row
numbers plus INVALID_ROW, never raw rows. Row numbers after parser filtering are
relative to the accepted batch in processing errors; original invalid-row numbers
remain in validation_errors. Failed source reads store classified history without
provider exception text. SecurityAudit retains the triggering actor/action/outcome.
A full database outage can prevent receiving/auditing an event; rerun the trusted
source after restoring PostgreSQL. No software transaction can persist through an
unavailable database.

## Validation and limits

Use `apps.integrations.postgres_test_settings`; it never loads shared .env or
DATABASE_URL. Tests exercise real imports/credentials, repeated and concurrent
imports, grade canonicalization, partial issuance recovery, payload conflicts,
source authorization, real Excel API/history, invalid workbook persistence,
interrupted runs, ZIP expansion and column bounds. Google API shape/parsing uses
injected clients; no claims of live Google authentication or 5,000-user throughput.
Shared issuer approval, migrations, source governance, scheduling, TLS/SMTP,
trusted proxy handling and gateway limits remain deployment responsibilities.

Legacy compatibility: pre-inbox spreadsheet achievement receipts with numerically
identical integer grades are replayed using their original evidence representation.
The shared receipt fingerprint and achievement UUIDs remain unchanged; genuine
payload differences still conflict. A PostgreSQL regression proves that an old
integer-grade Excel award can receive its missing credential without duplicates.
Valid Classroom previews are exempt from audit writes. Denied requests are logged
without parsing their bodies just to determine audit policy.

Final validation: 335 tests passed on isolated PostgreSQL; 337 discovered, two legacy
reference-schema tests explicitly excluded by the inherited runner. No concurrency
tests skipped. Migration drift and whitespace checks passed. End-to-end behavior
was exercised with synthetic Students/issuers and injected Google clients, not
shared Neon or live university/SMTP infrastructure. External Google destinations
normally include oauth2.googleapis.com and sheets.googleapis.com; configure allowed
network access and secure credentials through the deployment's approved settings.
