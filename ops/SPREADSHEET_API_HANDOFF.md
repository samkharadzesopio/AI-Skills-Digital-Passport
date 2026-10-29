# Flexible spreadsheet API handoff

All paths start `/api/integrations/`. These are additive backend contracts.
The Live Administrator Imports page now connects the reviewed profile workflow
through `admin/live/SpreadsheetImports.tsx` and its typed service/contracts.
Existing strict Excel/Sheets calls retain their responses when no profile is supplied.

Every endpoint below requires an active, verified, non-superuser Admin with the
existing exact `accounts.import_completions` grant. Session cookies and CSRF are
required for writes. Responses are `no-store`. A preview is private to its creator;
another importing Admin receives 404. General import histories keep their existing
permission scope. No source URLs, credentials, issuer selectors, profile definitions
or caller-supplied record bodies are accepted by confirmation.

| Method/path | Request and response |
| --- | --- |
| GET `import/profiles/?page=N` | Django numbered pagination, 50/page. Items: `id`, `key`, integer `version`, `source`, `kind`. Only enabled profiles. No private target, manifest or approval reference. |
| POST `import/excel/preview/` | Multipart exactly one `profile_id` and one `.xlsx` `file`. HTTP 201 preview. The existing `import/excel/` path also selects this workflow when `profile_id` is present. File-only requests retain strict immediate-import behavior. |
| POST `import/google-sheets/preview/` | JSON exactly `{"profile_id":"<approved Google profile UUID>"}`. HTTP 201 preview. The target is server-configured; no arbitrary URL, ID, worksheet or range. |
| GET `import/previews/<UUID>/` | Private preview status/report and current result, if any. |
| POST `import/previews/<UUID>/confirm/` | Exactly `{"confirm":true,"snapshot_sha256":"<reviewed digest>"}`. HTTP 200 current preview/result. Never upload a replacement file here. |
| GET `imports/` | Existing cursor-paginated run history. New runs retain the same envelope and include the aggregate result and safe original row classifications. |

A preview has `id`, `snapshot_sha256`, `state` (`READY`, `PROCESSING`, `COMPLETED`,
`FAILED`), `expires_at`, `report`, and nullable `result`. Reports contain:

```json
{
  "profile_id": "<UUID>", "profile_key": "<operator key>", "profile_version": 1,
  "source": "BTU_EXCEL", "kind": "SKILL_AWARD", "header_row": 4,
  "columns": {"external_student_id": 1, "source_event_id": 10, "skill_code": 11, "earned_on": 16},
  "total_rows": 75, "valid_records": 0, "duplicate_records": 0,
  "invalid_records": 15, "review_records": 60,
  "rows": [{"row": 5, "status": "REVIEW", "code": "INSTITUTIONAL_CONFIRMATION_REQUIRED", "message": "The source must explicitly record CONFIRMED. Pending, rejected or missing decisions cannot issue."}]
}
```

This example illustrates shape/missing approval, not configured institutional
eligibility. Row/column numbers are one-based and refer to the original source.
Blank rows are excluded from totals. `VALID` means eligible for the reviewed
import, never public or blockchain verification. `DUPLICATE` means an unchanged
evidence identity; conflicting copies block all copies. `REVIEW` never issues.
`INVALID` never issues. Only saved valid records are processed on confirmation.

The result includes `import_id`, `processed`, `awarded`, `issued`, `skipped`,
`failed`, `errors` (`row`, safe `code`) and `rows` (original `row`, execution
`status` `ISSUED`/`SKIPPED`/`FAILED`). Skill-award outcomes additionally contain
`receipt_id` and `credential_id` for authorized administration. No names, emails,
raw source values, private provider messages or Google configuration are returned.
`awarded` counts new achievements; `issued` counts credentials, not chain proofs.
Run state may be PARTIAL when invalid/review rows were excluded. Its history
retains those exclusions even when all eligible rows succeed.

HTTP 400 indicates an invalid file, mapping or control body. HTTP 403 retains
the existing permission/CSRF behavior; 404 covers wrong-owner/unknown previews
and profiles. HTTP 409 codes include `PREVIEW_DIGEST_MISMATCH`,
`SOURCE_CHANGED_REVIEW_REQUIRED`, `PREVIEW_EXPIRED`, `IMPORT_ALREADY_RUNNING`,
`PREVIEW_EXPIRED_OR_ATTEMPTS_EXHAUSTED`, `IMPORT_LEASE_LOST`, and
`NO_ELIGIBLE_RECORDS`. HTTP 503 codes include `GOOGLE_SOURCE_UNAVAILABLE`,
`SOURCE_PROFILE_DISABLED_OR_CHANGED` and
`INSTITUTIONAL_SOURCE_OR_ISSUER_NOT_CONFIGURED`. Messages are allowlisted or
fixed validation text, never provider exceptions. Preserve the existing gateway
and account error handling. Do not automatically replay confirmation POSTs.

The UI should select a saved profile, display the report and exclusions, obtain
explicit confirmation, then submit the exact digest. Excel executes its immutable
saved normalized snapshot. Google is re-read before execution; any content or
configured-target change requires a new preview. Once a run completed, repeat
confirmation returns its existing result rather than synchronizing newer data.
Use a new preview for each new remote snapshot. A transient failed run can be
explicitly retried against the same unexpired snapshot, at most five attempts.
An interrupted PROCESSING session becomes reclaimable after its five-minute
lease; committed rows replay idempotently. One-hour expiration also applies to
recovery. After expiration, create/review a new preview; existing receipts prevent
duplicate issuance. Do not treat a client cancellation as a server rollback.

The original completion event history/retry API still operates on completion
inbox UUIDs. New skill awards commit atomically and recover through the saved
preview, not by submitting their receipt UUID to the completion retry route.

Keep files/results in memory in the UI and clear private state on logout/account
switch. Never infer approval from `Passport Sync Status`, existing Passport IDs,
badge formulas or a local preview. The connected controls keep private state in
memory, remount on account changes, require explicit confirmation and never
automatically retry a confirmation POST. Strict completion controls remain available.

## Opt-in automatic Google awarded-skill discovery (PD-01 / PD-01a)

Existing manually reviewed imports retain the contract above. An importing
administrator can separately authorize recurring processing of an existing,
enabled, institutionally approved Google `SKILL_AWARD` profile. This uses the
existing `accounts.import_completions` grant and session/CSRF controls. No student
consent field, endpoint or control is added. Administrator source authorization
does not establish institutional academic approval or a legal processing basis.

- `GET /api/integrations/import/automatic-sources/?page=1` lists profiles/status.
- `POST /api/integrations/import/automatic-sources/<profile_uuid>/` enables with
  exactly `{"enabled":true,"confirm":true,"interval_seconds":300,
  "authorization_reference":"institutional continuing-authority reference"}`.
  The interval is an integer from 60 to 86400; the reference is required and at
  most 255 characters. Disable accepts exactly `{"enabled":false}`. Actor comes
  from the current authenticated administrator. Caller-selected actors, target
  IDs/URLs, records, profiles, credentials and issuers are rejected.
- `GET /api/integrations/import/automatic-sources/<profile_uuid>/history/?page=1`
  returns sanitized states, counts, error codes, timestamps and saved preview IDs.
  Responses never include private source rows/targets or authorization references.

The worker is a separate supervised integration process:
`python backend/manage.py poll_spreadsheet_sources --watch --limit 10`.
Without `--watch` it runs one bounded cycle. Enabling a source does not start the
worker. Do not run against a real institution or persistent database without the
required operator approval and source/credential/governance setup.

Automation defaults off. Enable pins the configured spreadsheet identity,
worksheet, normalized bounded range and immutable policy fingerprint. Drift
records `AUTOMATION_SOURCE_CHANGED_REAUTHORIZE` and cannot issue until explicit
reauthorization of a valid target. Existing approved-source, immutable profile,
fixed trusted issuer, exact student/skill matching, CONFIRMED-only processing and
Record ID deduplication remain mandatory. The active actor/grant and binding
lease are rechecked under each award transaction; disable/revocation prevents
later commits. Poll completion/recovery lock binding then poll to avoid stale
worker lock inversion. Provider reads remain outside database transactions.

Unchanged snapshots create no new imports or official versions. Provider failure
keeps the previous safe checkpoint, records a redacted error and can recover on
a later poll. Interrupted leases are reclaimable; stale workers cannot restore
disabled/re-authorized state or overwrite the new lease/history. Existing saved
failed previews reuse the bounded attempt budget when eligible. Issuance counts
still do not imply blockchain confirmation; existing Passport/publication/chain
workers and public proof verification remain authoritative.
