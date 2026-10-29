# Public third-party verification

The existing public interface is connected to Django's PostgreSQL credential, Passport/version and document registries. See [the implementation and acceptance report](../../../ops/THIRD_PARTY_VERIFICATION.md) for exact DTOs and test evidence.

## Routes

- `/verify`: public landing and methods.
- `/verify/reference`: choose credential, Passport or Passport version; submit a public reference.
- `/verify/reference?kind=credential|passport|passport-version&reference=...`: validated prefilling for direct links.
- `/verify/qr/:reference` or `/verify/qr?kind=...&reference=...`: QR-compatible entry URLs, with review before submission. Printed `passport:UUID` and `passport-version:UUID` references are supported. Duplicate/conflicting parameters are rejected.
- `/verify/upload`: one PDF up to 5 MiB, standard multipart, cancel and indeterminate upload/registry feedback.
- `/verify/result`: in-memory public result only. Reload or a `status=VALID` URL cannot restore/invent a result.

`validation.ts` normalizes references and constructs safe relative links. `adapters.ts` parses the real Django public DTOs and drops private/unknown fields. `service.ts` uses a public-only fetch client with credentials omitted, no referrer, no cache and redirect rejection. The public layout never requests account/Student/Admin data or mounts their session hooks.

## Results

Authenticity, latest-versus-historical currency, current credential validity and lifecycle counts are separate facts. A recognized PDF may be latest while an included credential is revoked/expired. That does not mean its bytes were altered. Unrecognized bytes are described as unconfirmed, not automatically proven tampered. Credential lookup exposes only the public reference and current status; it does not invent a separate authenticity flag absent from that DTO.

All authoritative decisions come from Django. Counts, stamps, format metadata, template artwork and QR links do not establish validity in React. Raw backend message/error text, private student records and PDF contents are not displayed/logged. Uploaded filenames are not needed by the registry and are transmitted as `passport.pdf`. Files/results are not put in localStorage or query caches.

For a REVOKED Passport/PDF response, the adapter projects only the bounded
`blockchain.passport_status` enum into `publicInfo.passportStatus`. A revoked
identity displays **Passport revoked**, while revoked supporting credentials
retain their separate heading. Missing lifecycle evidence uses **Revocation
reported** without guessing the cause. Both English and Georgian distinguish
these cases. This changes wording only: root status, credential validity,
historical currency and the independently checked blockchain badge remain
separate. No backend field, permission or verification rule is changed.
The public registry skips credential assessment for cancelled identities and can
return `credential_status=UNVERIFIABLE` even when an authorized Credential read
still reports VALID. The page preserves that unavailable public fact rather than
inferring that the academic credential was revoked or exposing private data.

## Configuration

The same-origin `/api/` client and exact PostgreSQL registry contracts are enabled by default in live mode. `VITE_PUBLIC_VERIFICATION_ENABLED=false` disables requests. An explicitly empty `VITE_PUBLIC_VERIFICATION_SOURCES` also disables requests. Defaults/expected labels are POSTGRESQL_CREDENTIAL_REGISTRY, POSTGRESQL_PASSPORT_REGISTRY and POSTGRESQL_DOCUMENT_REGISTRY; method-specific labels must match. These labels are not signatures or issuer trust grants; Django enforces current issuer policy. Simulated/test/mock responses remain rejected even if listed, and Demo Mode cannot perform official verification.

Production always uses same-origin `/api/`, even if an old Vercel environment
variable contains a direct backend URL. Optional `VITE_API_BASE_URL` is used only
by development servers, retaining safe same-origin/HTTPS and loopback HTTP
validation. Vercel must load `frontend/vercel.json` with Root Directory `frontend`
to forward API requests to Render. Public requests do not use Student login
cookies or private CSRF bootstrap; private API/session/CSRF behavior is unchanged.

## Tests and remaining scope

`npm.cmd run check:verification` covers DTO/response invariants, private-field rejection, lifecycle combinations, safe links, file limits, loading/cancel, sanitized failures and rate-limit cooldown. Its transport fixtures are tests, not application data. Build, lint, Student/auth/architecture/demo/Passport/Admin checks remain required.

Run `.\.venv\Scripts\python.exe ops/test_verification_e2e.py` from repository root with the documented disposable loopback PostgreSQL settings for actual React/Vite/Django/PostgreSQL acceptance. It uses real generated/downloaded PDFs and public UI submission without login; no verification response is mocked. The driver is jsdom, not a graphical browser.

QR image generation/device scanning and graphical/mobile/accessibility acceptance remain future work. No PDF template, blockchain implementation or production configuration was changed. [Future blockchain DTO coordination](../../../ops/BLOCKCHAIN_VERIFICATION_DTO_PROPOSAL.md) is a proposal only; no blockchain proof is claimed here.
