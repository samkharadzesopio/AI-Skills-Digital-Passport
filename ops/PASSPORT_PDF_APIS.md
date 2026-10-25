# Private Passport PDF APIs

Baseline: local `integration` at `b9343110dff8c664f4719867080855fd165fa001`.
Feature: `feature/passport-pdf-apis`. No integration/main merge or shared database migration.

## Routes and permissions

All routes use existing account session authentication, CSRF enforcement and
`Cache-Control: no-store`. The UUID in a historical URL is the internal PassportVersion
ID already returned by the private Passport APIs; public references do not authorize
private downloads.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/student/passport/pdf/` | Generate/reuse latest issued version PDF |
| GET | `/api/student/passport/pdf/status/` | Latest version document metadata |
| GET | `/api/student/passport/pdf/download/` | Stream latest issued document for latest version |
| POST | `/api/student/passport/versions/{id}/pdf/` | Generate/reuse own historical issued version |
| GET | `/api/student/passport/versions/{id}/pdf/status/` | Own historical document metadata |
| GET | `/api/student/passport/versions/{id}/pdf/download/` | Stream own historical issued document |
| POST | `/api/admin/passports/{id}/pdf/` | Generate/reuse selected issued version |
| GET | `/api/admin/passports/{id}/pdf/status/` | Selected version metadata |
| GET | `/api/admin/passports/{id}/pdf/download/` | Stream selected version's latest issued document |

Students must pass existing authoritative linked-account and `IsOwnPassport`
permissions. Every version lookup is scoped to the authenticated Student UUID;
the secure opening service rechecks ownership. Caller-supplied student IDs, document
references, filenames and storage paths are rejected.

Admin paths use internal DigitalPassport UUIDs. Generation requires
`accounts.manage_credentials`; status/download require `accounts.view_student_records`.
Existing active/email-verified ADMIN, staff and non-superuser rules apply. Admin
requests may select an existing issued version with `?version_id=<internal-version-uuid>`;
it must belong to the route's passport. The selector works consistently on all three
admin endpoints. Without it, the passport's latest issued version is selected.
There is no selector for a different student or arbitrary storage object.

POST bodies must be empty JSON objects (`{}`). All other fields are rejected.
Students accept no query parameters. Admins accept only one `version_id`; duplicate,
unknown and malformed selectors are rejected. GET routes support HEAD. Route names
are `student-passport-pdf-{request,status,download}`,
`student-passport-version-pdf-{request,status,download}`, and
`admin-passport-pdf-{request,status,download}`.

## Generation behavior

Generation calls `generate_passport_document` directly, with its existing document
fingerprint, hash, lease, protected storage keys and retry behavior. Bounded rendering
is synchronous; successful first requests and replays return 200. HTTP requests use
`wait_seconds=0` to avoid waiting on another renderer. A live lease returns 409 plus
`Retry-After: 2` and the persisted generation state. This does not enqueue work or
claim an asynchronous job was accepted; no 202 is fabricated.

The dispatch is marked `non_atomic_requests` so rendering runs outside request
transactions, including deployments that enable ATOMIC_REQUESTS. The service still
owns short claim/finalization transactions and rejects caller-held transactions.
No new queue, worker, document model, lifecycle, or renderer was introduced.

Generation requests share the existing PostgreSQL `AuthRateLimitBucket` infrastructure.
The hashed authenticated account budget spans current/historical requests across
workers: default 6 POSTs per minute, configurable via the Django setting
`PASSPORT_PDF_REQUESTS_PER_MINUTE` (1-1000). The setting may be set by a deployment's
settings module; no new environment variable contract is assumed. Replays/failures
also consume budget. Status polling and downloads do not consume generation budget.
Exhaustion returns 429 with Retry-After. Counts are stored using a separate digest
namespace and use the existing expiry/purge mechanisms.

## Metadata response

```json
{
  "document_reference": "<public-document-uuid-or-null>",
  "passport_reference": "<public-passport-uuid>",
  "passport_version_reference": "<public-version-uuid>",
  "status": "ISSUED",
  "generated_at": "2026-10-25T12:00:00Z",
  "available_for_download": true,
  "download_document_reference": "<public-document-uuid-or-null>",
  "error": null
}
```

`status` is NOT_REQUESTED when no document exists, otherwise PENDING, GENERATING,
ISSUED or FAILED. `document_reference`/`generated_at` describe the newest generation
attempt for the selected version. Download availability is based on issued metadata;
`download_document_reference` identifies the latest issued generation for that same
version. A prior issued generation can remain downloadable if a later renderer's
attempt is pending or failed. There is never a fallback across Passport versions.
Storage outages/missing files can still make a declared issued document unavailable
at download time; status requests do not open files or read PDF bytes.

Failed status responses expose only `GENERATION_FAILED`; they never expose persisted
exception text, error types, storage keys, filenames, lease tokens or paths. A failing
POST reports `PDF_NOT_REPRESENTABLE` (422) or `GENERATION_UNAVAILABLE` (503). Retrying
reuses the same document/fingerprint and increments the existing attempt counter.

## Downloads and errors

Downloads use `open_passport_document_for_student` after Student ownership or explicit
admin permission and version association are established. They return FileResponse,
`Content-Type: application/pdf`, an attachment filename
`btu-passport-<public-version-uuid>.pdf`, `Pragma: no-cache`, and
`X-Content-Type-Options: nosniff`. Django closes the opened file when the response
closes; construction failures close it immediately. No request value is used as a
filesystem path or filename. Possession of a public verification reference alone
never grants private access.

| Status | Meaning |
|---|---|
| 200 | Generated/reused, status returned, or file streamed |
| 400 | Unsupported body/query fields, malformed/duplicate selector |
| 403 | Authentication, linked identity, explicit admin permission or CSRF failed |
| 404 | Missing/foreign passport or issued version; no requested PDF to download |
| 405 | Unsupported HTTP method |
| 409 | Rendering lease active, or document exists but none issued for download |
| 422 | Snapshot information exceeds template/font/size/row bounds |
| 429 | Account generation request budget exhausted |
| 503 | Safe generation/storage failure; POST includes Retry-After: 5 |

Privileged POST generation and GET/HEAD downloads (including rejected attempts) use
`AuditedAPIView`/`SecurityAudit`. Only actor, action, hashed client address and HTTP
outcome are logged. Audit records describe the HTTP outcome, not proof of full file
delivery to the client. Status polling does not generate privileged read audit rows.

## Template and verification compatibility

`templates/Passport_Blank.pdf` and all three existing stamp assets are unchanged.
The existing PyMuPDF template renderer still supplies cover, stamps, skill supplements
and credential pages. Its field/box checks now fail explicitly when text would be
truncated, omitted, or exceed its supported font, rather than producing an incomplete
registered PDF. All skill supplement rows include frozen category/subcategory/level,
including skills beyond the cover's first ten cards. Existing skill/credential/byte
bounds remain in force.

Dynamic fields embed the bundled Noto Sans Georgian Regular/Bold fonts, covering
Georgian (including uppercase), English and numbers without system-font or runtime
network dependencies. Text is measured with those fonts inside the same template
boundaries. Glyphs absent from the bundled font and text that genuinely cannot fit
return 422; required content is never silently replaced or shortened. The template
artwork, font sizes and field positions are unchanged. Font provenance and licensing
are documented in `GEORGIAN_PDF_REPORT.md`; the SIL Open Font License accompanies
the font files in `backend/templates/`.

The renderer version is `pymupdf-template-v4-georgian-fonts`; both font binaries are
included in its fingerprint. Explicit new generation requests
use the existing renderer fingerprint/idempotency mechanism. Older issued documents,
public references, hashes and snapshots are not rewritten. Historical generation
reads frozen version facts, never mutable profile/skill values. The printed
`passport-version:<public-version-uuid>` format and public verification contracts
are unchanged. Registered-byte authenticity, latest-version currency, and current
credential validity remain separate: a historical PDF can be authentic and still
report REVOKED/EXPIRED through existing public verification.

## Validation and next steps

Current font validation and provenance are in `GEORGIAN_PDF_REPORT.md`; the original
API implementation checkpoint is recorded in `PASSPORT_PDF_REPORT.md`.
Only isolated loopback PostgreSQL was used. No shared Neon migration, deployment,
frontend change, integration merge, or main modification was performed.

Next: review the existing field-length policy with the university,
then jointly review the branch and run staging HTTP/storage/load checks before
frontend integration. Synchronous bounded rendering has not been throughput-tested.
