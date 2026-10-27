# Flexible Excel and Google Sheets integration

Feature baseline: `bec0d8323ff98cb9e4e83c51f607d23d1e9ab46a` (`origin/integration`,
freshly fetched). Work is isolated in `feature/flexible-spreadsheet-integration`
at `AI-Passport-spreadsheet-integration`. The primary frontend checkout remains on
integration. No persistent local database or Neon migration is authorized or run.

## Actual BTU workbook inspection

The supplied Downloads workbook was opened read-only. SHA-256:
`dd4e05d240713665d8b79c2fd582948512104667ea2b0deec130c7c8092c6770`.
It was neither modified nor copied into Git. Only aggregate structure/quality is
recorded here; tests create separate synthetic workbooks in memory.

`Passport Skill Records` has 20 columns, headers on row 4, and 75 nonempty rows:
60 populated skill awards for 18 distinct Students, plus 15 rows containing only
a Student ID. The 60 populated Record IDs are unique, with no repeated
Student/Skill pair or conflicting name/email/status per Student in these rows.
There are many empty rows/cells, including two blank rows inside the nonempty
source extent. Read-only sheet dimension metadata is absent, so the reader does
not rely on declared `max_row`/`max_column`.

Earned dates are ISO text between 2026-09-18 and 2026-10-18. Student statuses in
the populated awards are Active (53) and Graduate (7). Graduate eligibility needs
an explicit institutional decision; it is not inferred from being present.
There are 60 badge-code formulas. Sync outputs show SYNCED (16) and NOT SYNCED
(44); neither is a university approval decision. There is no approval field.
These are skill awards, not completions: no course IDs, grades or passing
decisions are invented.

| Source field | Controlled meaning |
| --- | --- |
| Student ID | Exact existing `Student.external_student_id`; never internal UUID inference or Student creation |
| Record ID | Stable evidence identity in an operator-approved namespace, shared across exports/channels |
| Skill ID | Exact existing `Skill.skill_code`, or explicitly approved exact ID value map; catalog allowlist required |
| Date Earned | Nonfuture earned date; explicit date formats, ambiguous dates fail |
| First/Last Name, email, Student Status | Optional consistency checks against existing Student; never identity edits |
| Skill Name/category/stamp | Optional checks against existing catalog; never catalog writes or proficiency claims |
| Badge/Stamp Code formula | Ignored unless mapped; mapped formulas are rejected, never evaluated |
| Existing Passport ID/first-issued and sync output columns | Ignored; prohibited as mapping aliases for evidence/approval |
| Institutional approval | Missing from supplied workbook. An institution-authorized source must supply explicit CONFIRMED; no defaults |

Structural analysis maps the 60 complete rows and rejects the 15 incomplete
rows. None of the supplied records can be considered eligible for issuance:
all 60 need approval evidence, registered Student associations, approved catalog
IDs/eligibility, trusted source and issuer configuration. No persistent database
was inspected to assert those associations. Merely collecting source Skill IDs
for the read-only analyzer is not provisioning an authorized catalog policy.

## Implementation

`importers/mapping.py` provides bounded exact header matching, explicit aliases,
case/Unicode/whitespace/separator normalization for headers, reordered columns,
extra-column handling, required fields, controlled value maps and dates. Sensitive
skill identifier value maps are exact after trimming, with no case, punctuation
or similarity guessing. Header detection scans at most ten rows. All copies of
a conflicting Record ID are blocked, including when another copy is invalid.

The profile is selected explicitly, not guessed from uploaded content. Profiles
are immutable versions installed by a trusted operator, disabled by default, with
an institutional policy approval reference. Enabling one does not approve rows
or provision an issuer. Existing `BTU_AUTHORIZED_COMPLETION_SOURCES` authorization
still applies, independently of the Admin import grant and enabled profile.
Both approval and current domain eligibility are rechecked before writes.

Excel remains bounded to 5 MiB compressed, 32 MiB archive expansion, 1,000 ZIP
members, 26 columns, 5,000 physical data rows and 16 KiB text per row. Missing or
false worksheet dimensions do not bypass iteration limits. Macros, external-link
parts and embedded objects are rejected. Evidence formula cells are rejected;
unmapped output formulas are ignored without evaluation. No formulas are exported
or executed. Invalid parser/provider values are never echoed to users or logs.

Three new tables retain profiles, actor-bound expiring reviewed previews, and
atomic skill-award receipts. Existing `ImportRun`, completion inbox, security
audit, achievement, credential, Passport and blockchain ledgers are reused.
Profile/preview inputs and committed award receipts have PostgreSQL immutability
guards. No previously applied migration was changed.

The existing achievement service already accepts `course_id=''`; the credential
service issues only verified achievements from the fixed trusted BTU issuer.
This supports explicit approved skill evidence without changing credential
semantics. Awards use `BTU_SKILL_AWARD` source receipts and a stable namespace plus
Record ID, preserving idempotency across profile versions, Excel and Sheets.
The namespace is an institutional identity boundary, not a client selector. Do
not change it to evade a conflict. Changed evidence cannot rewrite a prior award
or reissue a revoked credential. Cancelled Passports require the existing explicit
institutional replacement workflow; imports never reactivate them.

Skill achievement, credential and receipt commit in one database transaction.
Existing credential lifecycle scheduling handles Passport refresh; signing,
publication and chain confirmation remain existing separate worker responsibilities.
No blockchain contract, RPC policy, signing code or domain migration changed.
Confirmation never claims that issuance equals current blockchain verification.
Previews never create achievements, credentials, Passports, versions, PDFs or
blockchain operations. They do persist a private reviewed session and security
audit, so the institution must include these records in its data retention and
backup policy. The implementation retains reviewed inputs/audit history; no
unreviewed PII purge or history deletion was added.

Legacy file-only strict completions and configured legacy Google calls keep their
format and response. New flexible completion profiles use the same validators,
approved course repository and durable inbox; they cannot fabricate course facts.
If an approval column is configured, it is enforced in addition to completion
rules. Google authentication now requests a read-only Sheets scope in both paths.

## Operator configuration (future authorized environment only)

No profile, account, source approval or credential was provisioned in persistent
development, staging or production by this task. Review this example with the
institution; replace synthetic values with authorized identifiers/policy evidence:

```json
{
  "key": "approved-skill-awards", "version": 1, "source": "BTU_EXCEL",
  "kind": "SKILL_AWARD", "approval_reference": "<institutional source-policy approval reference>",
  "definition": {
    "worksheet": "Passport Skill Records",
    "evidence_namespace": "approved-university-skill-awards",
    "columns": {
      "external_student_id": ["Student ID"], "source_event_id": ["Record ID"],
      "skill_code": ["Skill ID"], "earned_on": ["Date Earned"],
      "approval_status": ["Institutional Approval"]
    },
    "allowed_skill_codes": ["<approved existing catalog code>"],
    "eligible_student_statuses": ["<approved exact Student status>"],
    "date_formats": ["%Y-%m-%d"],
    "value_maps": {"approval_status": {"CONFIRMED": "CONFIRMED", "PENDING": "PENDING", "REJECTED": "REJECTED"}}
  }
}
```

Use `manage.py provision_spreadsheet_profile --manifest <reviewed private JSON>`
only after separate target/migration approval. A separate explicit `--enable`
enables that reviewed profile. Existing versions cannot be edited; create a new
version for policy changes. A trusted operator may disable a profile using normal
Django management tooling; only its `enabled` field is mutable. No browser profile
CRUD/approval endpoint exists. No new capability or automatic grant was added.
Only authorized institutional administrators should have import permission.

Completion profiles map the seven existing canonical completion fields to explicit
aliases. Approved course mappings remain authoritative. No course IDs, grades,
passing rules, approval defaults, issuer overrides or source IDs can be supplied
as mapping constants. Profile header aliases cannot target system output columns.

## Google service account and live acceptance

1. Have the institution approve an independent source copy containing synthetic or
   properly anonymized data. Enable the Sheets API in the approved Google project.
2. Create a dedicated read-only service account, share only the approved spreadsheet
   with that account as Viewer, and store its credential file outside Git/browser
   paths with restricted OS access. No credential is returned by any endpoint.
3. Set existing server-only `GOOGLE_SERVICE_ACCOUNT_FILE`. Configure
   `BTU_SPREADSHEET_GOOGLE_SOURCES_JSON` as a JSON dictionary, for example
   `{"approved_awards":{"spreadsheet_id":"<approved ID>","worksheet":"Passport Skill Records"}}`.
   This is a server target registry, not a request parameter. Keep it private.
4. Provision a separate `BTU_GOOGLE_SHEETS` profile with the same authorized
   evidence namespace, the exact worksheet, and `definition.google_source` set to
   `approved_awards`. Independently approve that channel through the existing
   source policy; retain the fixed trusted BTU issuer.
5. Read uses only A1:Z5011 (ten header candidates plus bounded data/overflow detection),
   formula rendering to detect evidence formulas, a 5-second connect/10-second read
   timeout and at most three idempotent read attempts on timeout/connection/429/5xx,
   with short bounded backoff. Authorization/configuration failures are not retried.
6. Through an authorized real session, preview, inspect exclusions, confirm the
   exact digest, inspect histories, repeat to prove no duplicate issuance, change
   the sheet after a preview to prove 409, and check unavailable/permission failures.
   Review actual issuer/source approval and worker/lifecycle/chain outcomes before
   making institutional claims. Never test by modifying the original BTU dataset.

No live credentials were provided or exercised. Provider fixtures test access
failures, timeouts/retries, exact range, scopes, changed snapshots and the shared
mapping plus real PostgreSQL issuance. This does not prove live Google access.

## Validation

Run `ops/run_isolated_tests.py --spreadsheet --backend --chain-http` with the
existing compatible Python environment and PostgreSQL 18 binaries. Set
`PASSPORT_ANVIL_BIN` to the pinned native Anvil executable when not installed in
this feature worktree. The launcher creates a new random loopback cluster and
owned databases, never loads production `.env`, and stops/removes only its own
resources. No persistent local/Neon migration is performed. Actual workbook
inspection is separately reproducible with `ops/inspect_btu_workbook.py <path>`.

Fresh local results (27 October 2026):

| Check | Result |
| --- | --- |
| All nine backend apps, including blockchain, authentication, Student/Admin APIs, credentials, Passports/PDFs, verification and integrations | 596 passed in 373.337 seconds; 598 discovered, with only the same two pre-existing legacy reference-SQL comparisons excluded by the unchanged baseline runner |
| Final focused spreadsheet and migration tests | 38 passed in 25.392 seconds, including every-existing-table preservation across integration/0002 upgrade with signed confirmed Anvil history |
| Real spreadsheet HTTP acceptance | 13 requests passed: session login/context, permission denial, CSRF denial, owner-bound preview, confirmation, wrong digest, replay and logout |
| Existing real blockchain/backend HTTP acceptance | All 11 journeys passed: OTP/session, authorized strict import through real PDF/confirmed proof, new versions, public exact/altered bytes, revocation, legal replacement, outage/recovery, least privilege, replay/no reactivation |
| Django check and migration drift | Pass; no changes detected |
| Disposable resource safety regressions | Six resource-manager tests plus three database cleanup tests passed; each cluster/DB/server/mail/media/signer resource owned by these runs was cleaned up |
| Actual workbook read-only analyzer | 60 structural awards, 15 incomplete rows, no approval column; unchanged SHA-256 |
| Git whitespace | Pass |

No existing assertion, query budget or concurrency test was weakened or removed.
The first focused attempt found a nullable-join `FOR UPDATE` error in new result
finalization; the lock now explicitly targets the preview row. Test-only setup
errors (an empty-grant administrator rejected by the existing account manager and
an overbroad new harness cache-header assumption about CSRF bootstrap) were fixed
without changing authentication policies. Final results above are fresh passes,
not totals reused from earlier milestones. The strengthened table comparison was
rerun after review; executable application code was unchanged after the full run.

No frontend or contract/signing implementation was edited, and no graphical
browser or live Google acceptance is claimed. Source remains local on the feature
branch; no merge/push or persistent migration occurred. See
[API handoff](SPREADSHEET_API_HANDOFF.md) and
[migration runbook](SPREADSHEET_MIGRATION_RUNBOOK.md).

Institutional gates remain: explicit record approvals, approved namespace/catalog/
status mappings, registered identities, trusted issuer and source governance,
Google service credentials/live acceptance, retention/operational review and a
separate frontend implementation. This feature is backend implementation with
synthetic acceptance, not completed institutional or production certification.
