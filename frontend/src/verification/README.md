# Public third-party verification

## Routes and behavior

- `/verify`: BTU landing page, reference/PDF methods and verification-process explanation.
- `/verify/reference`: explicit reference submission. Passport and credential scopes are distinct.
- `/verify/upload`: single-file selection or drag-and-drop, filename/size, client type/size validation, cancelable multipart submission, transport progress and waiting-for-verification state.
- `/verify/result`: in-memory result only. A URL, QR code, query parameter, browser history state or localStorage cannot supply a valid result. Reloading shows that no check has been performed.
- `/verify/qr/:reference` or `/verify/qr?reference=…`: reviews and prefills a passport reference. An optional `kind=credential` selects credential lookup. Ambiguous/invalid references are rejected. QR links do not automatically submit requests or prove authenticity. The frontend does not generate official references, QR codes or official verification URLs.

`VerificationLayout` and `VerificationProvider` are independent of student/admin layouts, session queries, private API clients and demo data. Only the language preference uses browser storage; no PDFs or results are stored there. Result state contains an allowlisted public DTO, not an uploaded file or raw API response. All new copy supports English and Georgian.

## Backend inspection and confirmed contracts

Read-only inspection covered `backend/config/urls.py` and `backend/apps/verification/{urls,views,serializers,document_serializers,services,document_service,repositories,document_repository}.py`.

Confirmed public routes:

- `GET /api/verification/{credential_id}/`: fields `credential_id`, `status`, `verified`, `source`; statuses `VALID`, `REVOKED`, `EXPIRED`, `INVALID`, `NOT_FOUND`.
- `POST /api/verification/document/`: multipart field `file`; PDF limit **5 MB**, not the old frontend's 10 MB. Fields `status`, `authentic`, `is_latest`, `passport_version`, `latest_version`, `message`, `source`; statuses `VALID`, `OUTDATED`, `INVALID`, `UNVERIFIABLE`.

Both views are `AllowAny`, but their default services currently use mock repositories and return `SIMULATED_CREDENTIAL_REGISTRY` or `SIMULATED_DOCUMENT_REGISTRY`. **These responses are never displayed as official success, invalidity, revocation or expiration.** They produce an unavailable/simulated-source result.

The generated passport document uses `passport-version:<UUID>` (and the legacy generator uses `passport:<reference>`). The current public URLconf has no passport or passport-version reference lookup endpoint. UUID-based references from the database-backed generator can be validated syntactically, but lookup returns integration-unavailable without sending them to the credential endpoint. Legacy non-UUID passport identifiers require a confirmed backend format/adapter before they can be accepted. Credential lookup follows Django's single path-segment contract with a 512-character UI transport bound; no invented institutional credential regex is imposed.

## Authoritative result handling

`service.ts` validates required fields, exact enum/boolean consistency, matching credential references and positive/consistent document versions. Unknown/malformed responses are technical failures. Only configured, approved source identifiers are admitted; simulated/mock/demo/test sources remain rejected even if added to the allowlist.

Rendered public information is restricted to the returned credential reference, version numbers, latest-version flag, registry source and explicit status. No private student profile is fetched. Extra fields and arbitrary backend messages/errors are not displayed or logged.

Reference `REVOKED`/`EXPIRED` and document `OUTDATED` have distinct views. `UNVERIFIABLE` is neutral and is not proof of tampering. The document contract does not yet have explicit revoked/expired states; the frontend does not infer them by parsing `message`. A bare HTTP 404 is a technical endpoint failure; only an authoritative JSON `NOT_FOUND` response represents an unknown reference.

HTTP 400/413/415/422 indicate a rejected request, never automatic document invalidity. HTTP 401/403 do not trigger a login flow. Network errors, timeouts, server errors and HTTP 429 are distinct from registry invalidity. Rate limits honor `Retry-After` seconds or HTTP dates, with a 60-second fallback; the cooldown is shared between public forms for this mounted session. There are no automatic retries. Django must enforce actual server-side limits.

## Deployment dependencies

Public transport is opt-in until a real registry is approved:

- Keep `VITE_PUBLIC_VERIFICATION_ENABLED=false` and `VITE_PUBLIC_VERIFICATION_SOURCES` empty for the current simulated backend.
- After backend approval, set the enabled flag and comma-separated exact authoritative source identifiers in deployment configuration. These are public configuration values, not credentials. This does not itself make a registry authoritative; Django must perform real verification.
- Confirm `VITE_API_BASE_URL` (default `/api/`), source identities and deployment routing. Production accepts same-origin paths or HTTPS API origins; local HTTP is allowed only in development. Public fetch transport omits login credentials and referrers, disables caching and rejects redirects. Cross-origin deployment requires appropriate server CORS configuration.
- Implement/wire a real passport-reference endpoint and its public response schema. Do not add an assumed route or map passport references onto credential IDs.
- Wire actual registry repositories and remove simulated provenance only when verification is truly authoritative. Confirm public field minimization, document revocation/expiration semantics, rate limiting, upload policy/retention, source identity and allowed error states.

Uploads remain in component memory until explicit submission. Client checks only use filename, browser MIME metadata and byte size; they do not parse PDF contents, compute authenticity or trust a PDF header. Server-side byte validation and registry matching remain authoritative. The upload progress bar reports transport progress only; 100% is not a verification result. Cancellation aborts the browser request but cannot guarantee a request already received by Django was not processed.

## Validation

`npm.cmd run check:verification` covers input/file boundaries, response invariants, allowlisted public fields, simulated-source rejection, HTTP error mapping, rate limits and result rendering. `check:architecture` checks public route independence and prevents URL-supplied result state. Student/Admin checks remain required.

Browser file-selection/drag-and-drop, real HTTP transport/progress, QR-device behavior and live Django registry checks still require integration/browser testing. No official successful result can be demonstrated with the current mock backend.
