# Third-party verification integration — 26 October 2026

Public React verification is connected to the existing Django PostgreSQL registries in the primary `AI-Skills-Digital-Passport` checkout on `integration`. This milestone changes frontend adapters/transport/presentation and test/documentation files only. No backend service, model, migration, worker, signing key, PDF template, blockchain code, or shared/Neon configuration was changed. All existing branches, worktrees, stashes, ignored local configuration and unrelated developer edits are preserved.

## Connected routes and behavior

- `/verify`: existing public landing and reference/upload entry points.
- `/verify/reference`: explicit credential, Passport or Passport-version lookup. Supports public UUIDs and printed `passport:UUID` / `passport-version:UUID` references.
- `/verify/reference?kind=credential|passport|passport-version&reference=...`: validated, prefilled direct links. Results require an actual API submission, not a URL status parameter.
- `/verify/qr/:reference` or `/verify/qr?kind=...&reference=...`: validated QR/URL entry points; printed prefixes infer the kind. Duplicated, conflicting or malformed parameters are rejected. A bare UUID needs its reference kind or defaults to Passport lookup. Users review and submit explicitly; following a link is not an authenticity verdict.
- `/verify/upload`: standard multipart PDF submission, nonempty `.pdf`/MIME metadata checks and a **5 MiB** limit, cancel and meaningful indeterminate feedback.
- `/verify/result`: allowlisted public results kept in memory. Refresh shows no prior result; no PDF/result is restored from browser storage or a claimed `status=VALID` query.

Student credential details now link to the correctly prefilled credential flow. The issued Passport preview links to current Passport lookup and a version-specific public QR entry URL. No QR image, scanner, cryptographic signature or PDF artwork was added; existing QR-compatible URLs can be encoded by a future QR producer without inventing verification evidence.

## Actual Django response contracts

No endpoint or serializer was changed.

| Endpoint | Public DTO |
|---|---|
| GET `/api/verification/{credential_reference}/` | `credential_id`, `status`, `verified`, `source`; status VALID/REVOKED/EXPIRED/INVALID/NOT_FOUND. `verified` is true only for VALID. No separate authenticity/currency field is provided for credential references, so the UI does not invent one. |
| GET `/api/verification/passport/{passport_reference}/` | `status`, `authentic`, nullable `is_latest`, nullable `passport_version`/`latest_version`, `credential_status`, `credential_counts`, `source`. Status VALID/OUTDATED/REVOKED/EXPIRED/INVALID/NOT_FOUND/UNVERIFIABLE. |
| GET `/api/verification/passport-version/{version_reference}/` | Same Passport DTO, scoped to the public version reference. |
| POST `/api/verification/document/` | Multipart `file`; Passport-like DTO plus `message`, with status VALID/OUTDATED/REVOKED/EXPIRED/INVALID/UNVERIFIABLE. Arbitrary backend message text is deliberately not displayed or retained. |

`credential_status` is VALID/REVOKED/EXPIRED/INVALID/UNVERIFIABLE. Nonempty counts contain VALID/REVOKED/EXPIRED/INVALID integer counts. Empty counts and null version facts remain unknown; they never become a locally inferred positive verdict.

`frontend/src/verification/adapters.ts` explicitly projects these actual contracts. It validates field types, statuses, nullable facts and structural consistency, then discards extra/private/future fields. It preserves the server's status and counts rather than calculating a new aggregate decision. The expected exact source is `POSTGRESQL_CREDENTIAL_REGISTRY`, `POSTGRESQL_PASSPORT_REGISTRY` or `POSTGRESQL_DOCUMENT_REGISTRY` for the corresponding method. These labels are response contracts, not signatures or issuer trust decisions; Django's current issuer/source policy remains authoritative.

`validation.ts` normalizes public references, safely encodes one path segment, dispatches the correct kind, rejects unsafe input and builds relative public links. Internal Student/Credential/Passport row UUIDs are never substituted by the application for public references. A backend NOT_FOUND response is distinct from an HTTP 404 route/transport failure.

## Independent result facts

The employer-facing result separately displays authenticity, latest/historical version currency, current credential validity and associated lifecycle counts. An authentic latest snapshot may have revoked/expired support. It is still described as recognized by the registry, with revoked/expired support shown independently; it is not described as altered merely because validity changed. An authentic UNVERIFIABLE snapshot also remains authentic while current support is unknown.

Modified or unregistered PDF bytes produce an unconfirmed registry result. The UI does not claim that this alone proves tampering. No verification decision is inferred from local PDF format, template artwork, credential counts, stamps, a QR link or browser data. Every result states that no blockchain proof was assessed.

## Transport, configuration and privacy

Same-origin `/api/` and the existing PostgreSQL source contracts are enabled by default in live mode. `VITE_PUBLIC_VERIFICATION_ENABLED=false` explicitly disables requests, and an explicitly empty `VITE_PUBLIC_VERIFICATION_SOURCES` fails closed. Optional configured sources must still match the exact method's registry. Simulated/mock/test registries remain rejected even if listed. Demo Mode always blocks verification; `.env.example` now documents real registry defaults instead of the obsolete mock-backend assumption.

Public traffic uses a separate Axios/fetch client with credentials omitted, no private CSRF bootstrap, no referrer, no-store and redirect rejection. Public layouts never mount account/Student/Admin queries. Failure states expose safe messages; backend payloads, names, emails, grades, private IDs, storage locations and PDF contents are not logged/displayed by this integration. Reference URLs contain only intentionally public references. The transmitted filename is the generic `passport.pdf`.

The real HTTP test identified that Axios fetch progress tracking changes FormData into a chunked upload rejected by Django's development server. Standard native multipart now works through Vite/WSGI; the UI shows indeterminate upload/registry waiting feedback rather than fabricated percentages. Cancellation aborts the client request but cannot retract work already received by the server. PDFs remain only in the selecting component/request memory, never localStorage or result/query state. Existing backend upload bounds, hash matching, throttles, no-store responses and private session/CSRF protections are unchanged.

Retries return to the submitted public reference or upload form; they do not replay POSTs automatically. Retry-After cooldown is enforced immediately by request guards and disabled retry presentation.

## Fresh test evidence

| Check | Result |
|---|---|
| Full combined Django suite including verification, authentication, Student APIs, credentials, Passports/PDFs and local-profile boundary | **466 passed in 158.581 seconds**; 468 discovered, same two existing legacy reference-SQL comparisons explicitly excluded by the existing runner |
| `check:verification` | PASS: actual DTO/status projections, valid/revoked/expired/unknown results, independent authentic/currency/support facts, malformed responses/counts, private-field and simulated-source rejection, safe reference/QR routing, upload limits, loading/cancel, rate-limit cooldown and sanitized failures |
| TypeScript/production build and lint | PASS; existing large-bundle warning remains |
| `check:student`, `check:auth`, `check:architecture`, `check:demo`, `check:passport`, `check:admin` | PASS |
| `check:preview` | PASS with the demo flag supplied only to the check process; ignored configuration files were not changed |
| `ops/test_verification_e2e.py` | PASS: **35 real proxied requests**, actual Django services and disposable PostgreSQL; jsdom renders the public React interface, no verification/API responses mocked |
| Existing `ops/test_student_e2e.py` | PASS: **67 real proxied requests**, login/session restoration, records/PDFs, public byte verification, logout/cache cleanup, cross-owner and missing-CSRF denials |

The public acceptance fixture issues real synthetic credentials/versions using existing domain services. It authenticates a synthetic least-privilege administrator over HTTP only to generate/download four PDFs through the existing secured API, then logs out before public UI acceptance. It tests valid/revoked/expired/unknown credentials, latest and historical Passport/version references, printed/direct/QR entry links, real current/historical/revoked-latest/expired PDF uploads, modified PDF bytes, unsupported/oversized selection, actual PostgreSQL 429 behavior and private Student access denial. Public requests omit cookies/Authorization/CSRF, never bootstrap private APIs, and expose no fixture private fields. Registry assertions confirm four issued PDFs and no new documents caused by public uploads.

Revoked-latest fixture processing deliberately delays only the existing Passport outbox consumer, representing worker lag; verification responses themselves are not mocked. The expired fixture uses a real earlier effective snapshot and actual current expiration evaluation. Test databases and generated documents are isolated and removed by the test harness; local development/shared production records and developer files are untouched.

The first HTTP run failed on chunked upload; that transport issue was fixed before acceptance passed. Intentional early 429 rejection can emit WSGI/Vite connection-reset diagnostics while the expected 429 response and UI cooldown still pass. The existing Student DOM driver can emit nonfatal React `act` timing warnings. Neither test claims graphical-browser rendering, device QR scanning, mobile/keyboard accessibility, live institutional API access, live SMTP, production performance or blockchain proof.

## Reproduce

With locked frontend dependencies installed and the existing virtual environment, set the loopback PostgreSQL variables documented in `STUDENT_INTEGRATION.md`, then run from repository root:

```powershell
$env:FOUNDATION_TEST_PG_HOST='127.0.0.1'
$env:FOUNDATION_TEST_PG_PORT='55435'
$env:FOUNDATION_TEST_PG_PASSWORD='local-test-unused'
$env:AUTH_TEST_PG_PORT='55435'
.\.venv\Scripts\python.exe ops/test_verification_e2e.py
```

The harness uses safe test settings and an ephemeral backend/Vite port; it does not load production `.env`, migrate Neon, or expose a test-control endpoint. Public UI unit/contract transport uses explicit test fixtures and is separate from this real Django acceptance.

## Remaining scope

No graphical browser or camera/QR image generation was added. Production still needs its normal approved same-origin deployment, institutionally approved issuer/source policy and operational limits. Existing simulated Classroom access remains simulated. Admin frontend, Student redesign, SMTP, Neon and blockchain implementation are outside this milestone. Proposed future blockchain DTO needs are recorded separately in `BLOCKCHAIN_VERIFICATION_DTO_PROPOSAL.md`; no such field is returned, consumed or claimed as implemented here.
