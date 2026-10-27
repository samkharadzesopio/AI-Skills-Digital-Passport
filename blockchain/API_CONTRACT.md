# Passport lifecycle contract for React, Chrome and authorized Classroom viewers

This backend feature does not copy the website or create an alternative Passport design. All clients use the same existing self-scoped Django APIs and exact stored PDF bytes. The Chrome implementation remains a separate, paused task; these are its server contracts, not a claim that an extension has been implemented.

## Current student Passport

`GET /api/student/passport/` requires the existing active verified linked Student session. It accepts no Student selector. The existing object shape is retained, adding `lifecycle_status`, `first_issued_at` and `blockchain`.

- `{"passport": null}` means no active identity. Never fall back to a cancelled Passport cached by the client.
- `lifecycle_status` is ACTIVE, REPLACED or REVOKED. This student endpoint only returns ACTIVE identities; cancellation history is admin-only.
- Root `status` is NOT_ISSUED, PENDING_BLOCKCHAIN, UNVERIFIABLE or BLOCKCHAIN_VERIFIED in the production enforcement policy, with REVOKED/EXPIRED/INVALID taking precedence when represented credentials lose validity. Database snapshot `latest_version.status=ISSUED` by itself is **not** a blockchain verification result.
- Only show the BLOCKCHAIN VERIFIED label if root status is BLOCKCHAIN_VERIFIED, nested status is CONFIRMED and `blockchain_verified`, `issuer_key_authorized` and `institutional_issuer_approved` are all true in the same fresh response.
- `public_reference` is the permanent public Passport identity. `latest_version.public_reference` is a separate public version identity. The internal UUID `id` and Student UUID are not verification codes.

Legal replacement changes both public identities, the PDF and its proof. The Student UUID and academic records remain stable. Discard the old Passport cache on replacement/focus/reconnect and refetch the current endpoint. Do not choose a Passport by a client-supplied Student ID or keep an old identity as current during a retry.

## PDF APIs

Existing routes are unchanged:

- POST `/api/student/passport/pdf/` with `{}`: idempotent generation, existing session CSRF required.
- GET `/api/student/passport/pdf/status/`: metadata/status.
- GET `/api/student/passport/pdf/download/`: exact private generated PDF bytes.
- Version-specific routes under `/api/student/passport/versions/<internal version UUID>/pdf/...`: only versions of the current ACTIVE identity are available to Students.

Metadata adds `blockchain`, separate from the PDF artifact's own status/availability. A downloadable issued PDF can still be pending blockchain confirmation or have an issuer configuration error. Show that pending/error state explicitly. Never call it blockchain-verified based on `available_for_download=true` or document status ISSUED.

Loading/empty/expired-session/error states remain necessary. Treat 401/403 as an access/session failure, 404 as missing/unavailable authorized content, 409 as generation in progress, 422 as an unsupported template payload and 503 as generation/storage failure. The viewer must not rewrite, watermark, reconstruct or re-stamp the official bytes; that changes their hash. Display status outside the original PDF.

After legal cancellation, Student access to the old identity's PDF/version routes returns 404. Exact permissioned admin PDF routes retain historical access and audit the download. An already downloaded file cannot be erased from someone's computer; its public reference/PDF verification returns REPLACED/REVOKED.

## Public verification

No login/cookies are required for:

- GET `/api/verification/passport/<public Passport reference>/`
- GET `/api/verification/passport-version/<public version reference>/` (also accepts the printed `passport-version:...` reference)
- POST `/api/verification/document/` with multipart field `file`
- GET `/api/verification/blockchain/document/<public document reference>/`

The first three preserve existing fields: status, authentic, is_latest, passport_version, latest_version, credential_status, credential_counts and source. Their additional `blockchain` facts must be parsed separately. Unknown reference returns NOT_FOUND. Uploading changed bytes cannot inherit the original file's proof.

| Public status | Meaning |
|---|---|
| VALID | Current identity/version, currently valid credentials (when present), trusted configured issuer and an independently validated confirmed commitment on the configured registry |
| OUTDATED | Authentic earlier version of an active identity; do not present as the latest Passport |
| REPLACED | Identity cancelled for approved replacement; never current/valid, even if its old chain record remains authentic |
| REVOKED | Institution or registry explicitly invalidated the identity/represented credential |
| EXPIRED / INVALID | Existing credential-related invalidity, or integrity/trust invalidity |
| PENDING_BLOCKCHAIN | An actual pending issuance/confirmation; nested FAILED or NOT_CONFIGURED instead produces UNVERIFIABLE |
| UNVERIFIABLE | Chain/issuer trust/integrity cannot be established; never render a positive badge |
| NOT_FOUND | Unknown public reference |

`authentic=true` is historical registered-document authenticity, not a current-validity badge. `is_latest` describes version currency. A replaced identity always has `is_latest=false` even though its immutable internal last-version pointer remains for audit.

The chain object uses:

- `status`: NOT_CONFIGURED, PENDING_BLOCKCHAIN, FAILED, CONFIRMED, UNVERIFIABLE, UNAVAILABLE or NOT_FOUND.
- `blockchain_verified`: live-confirmed, currently ACTIVE identity and latest-version commitment with currently valid represented credentials. It is false for cancelled identities and revoked/expired/invalid credentials, including while snapshot refresh is pending.
- `registry_status` and `credential_status`: current institutional checks, when available after independent chain verification. A historical confirmation does not override credential revocation.
- `historical_blockchain_authentic`: independent proof of the original on-chain commitment; can remain true after replacement/revocation.
- `issuer_key_authorized`: the pinned access-controlled registry accepted this signer at issuance; later issuer-key rotation does not rewrite that history.
- `institutional_issuer_approved`: the fixed BTU database issuer exists, is trusted and is on the server verification allowlist. False means approval has not been established in this assessment. It is separate from on-chain signer authorization and requires no university website publication.
- `assessed_at`: timezone-aware ISO-8601 time when this request's assessment finished; null when transport is disabled or deployment configuration is invalid and no assessment occurred. A timestamp alone is not evidence of successful verification.
- `operation_state`: durable worker state (PENDING, SIGNED, SUBMITTED, CONFIRMED or FAILED), when an operation exists. This can remain CONFIRMED during a reorganization/RPC outage; use live `status` and flags for badges.
- `operator_review_required`: true for exhausted/terminal failures, a stuck submission or an externally consumed nonce. It never grants permission to re-sign or reset a nonce.
- `environment`: LOCAL_ANVIL or POLYGON_AMOY. Never display Anvil data as a public Amoy deployment.
- When available: chain_id, contract_address, issuer_address, transaction_hash (null before signing), block_number, block_hash, confirmations, onchain_status, opaque keys, commitment, commitment_salt, pdf_sha256 and snapshot_sha256. A known signed hash remains available during pending confirmation or RPC outage; block fields come from live validated evidence.
- `replacement_transaction_hash`: confirmed old-key cancellation dependency for a replacement PDF.
- `error` and `retryable`: bounded classifications; no raw provider errors, signing data, storage paths or private keys.

REPLACED/REVOKED are authoritative immediately after institutional cancellation, even while its on-chain cancellation is pending. `onchain_status` honestly reports the separately observed contract state. No former legal name or successor's public reference is disclosed by the old public lookup.

Verification uses the server's configured registry, on-chain issuer authorization and existing trusted database issuer. There is no BTU website declaration gate. The former `institutional_identity_verified` and `issuer_identity_url` fields have been removed; clients should use the root status and `blockchain_verified` flag above.

## Registrar mutation

POST `/api/admin/students/<Student UUID>/legal-name-change/`:

```json
{
  "expected_passport_reference": "CURRENT_PUBLIC_PASSPORT_UUID",
  "first_name": "APPROVED_NEW_FIRST_NAME",
  "last_name": "APPROVED_NEW_LAST_NAME",
  "idempotency_key": "STABLE_REGISTRAR_REQUEST_KEY",
  "evidence_source": "BTU_REGISTRAR",
  "evidence_reference": "PRIVATE_APPROVED_INSTITUTIONAL_RECORD_REFERENCE",
  "reason": "PRIVATE_APPROVAL_REASON"
}
```

This is a schema example, not actual identity evidence. The administrator must have `accounts.manage_legal_identity`; the server must authorize the evidence source. POSTs require the existing CSRF bootstrap/header and a real admin session. The service validates source, actual name difference, idempotency and the expected current reference. It records the administrator's approval, not a student's self-declaration. BTU must supply its real approval process; an arbitrary URL/file upload does not become trusted evidence.

Successful response: `event_id` and the newly current `passport` object, initially pending. Replaying the exact request returns that replacement; a conflicting key or stale expected identity returns 409. An approved correction remains committed and pending if issuer/chain configuration is unavailable; its durable audit intent is queued when configuration recovers. Missing chain configuration must never keep the cancelled identity current. Database/schema failures are not reported as successful approvals. Unknown inputs are rejected.

POST `/api/admin/passports/<internal Passport UUID>/revoke/` takes idempotency_key and reason, and requires `accounts.manage_passport_lifecycle`. No admin permission is granted automatically by the migration.

GET `/api/admin/students/<Student UUID>/passport-lifecycle/` is paginated, requires the registrar capability and audits the access. It exposes private approval references/reasons and historical public links only to that authorized administrator. Never fetch it from Student or public layouts.

## Independent transaction check

Save the public document proof object as JSON, obtain the actual PDF and choose an independent RPC reporting the expected chain. Run:

```text
python blockchain/scripts/verify_transaction.py --rpc-url APPROVED_HTTPS_AMOY_RPC --chain-id 80002 --registry-address ACTUAL_REGISTRY --proof-json proof.json --pdf passport.pdf --confirmations 3
```

The tool has no PostgreSQL access or signing key. It recomputes the salted PDF/snapshot commitment and checks the pinned contract, signer, exact input, event, canonical receipt, confirmations, current contract lifecycle and any replacement dependency. It needs no university website access. A transaction hash alone proves neither the contents of an arbitrary PDF nor current institutional status.

The tool intentionally reports `institutional_current_status=NOT_CHECKED`: on-chain integrity alone cannot establish a still-pending institutional cancellation. Combine the independent chain check with the authoritative public BTU lifecycle API. It never emits a blanket VALID/MVP-complete result.

## October 27 stabilization and response examples

`API_EXAMPLES.json` contains complete illustrative response objects for no Passport, a current verified Student Passport, public pending/verified/unavailable/failed verification, replacement, revocation, expired/revoked credentials and historical versions. Identifiers and hashes are synthetic examples, not evidence of a deployment. Existing response fields remain; the `blockchain` DTO is additive except for the explicitly removed website-declaration fields.

| Situation | Public root status | Live blockchain status | UI action |
|---|---|---|---|
| No current Student Passport | Student endpoint returns exactly `{"passport":null}` | Absent | Empty state |
| Issued, not yet anchored / insufficient confirmations | PENDING_BLOCKCHAIN | PENDING_BLOCKCHAIN | Pending; no positive badge |
| Current, valid, independently confirmed | VALID | CONFIRMED, all three approval/current flags true | Verified; show actual network |
| RPC timeout/outage | UNVERIFIABLE | UNAVAILABLE | Verification unavailable; discard any cached positive badge |
| Invalid deployment configuration | UNVERIFIABLE | NOT_CONFIGURED | Configuration unavailable |
| Exhausted or terminal operation failure | UNVERIFIABLE | FAILED | Failure/recovery state; not an endless pending spinner |
| Replaced / revoked identity | REPLACED / REVOKED | Any | Never current; historical proof can still be authentic |
| Revoked / expired represented credential | REVOKED / EXPIRED | May be CONFIRMED | No current verification badge |
| Authentic previous version | OUTDATED | May be CONFIRMED; current flag false | Historical authenticity only |
| Unknown public reference | NOT_FOUND | Absent or NOT_FOUND | Not found; absence of proof means not assessed |

Public verification endpoints return HTTP 200 for these business outcomes. Bad selectors are HTTP 400; throttling is 429. Private endpoints continue to return 401/403 for authentication/permissions and 404 for unavailable authorized historical content. PDF generation status and blockchain status are separate.

An issued empty snapshot can retain CONFIRMED historical document integrity, but its public root remains UNVERIFIABLE and blockchain_verified is false: no represented valid credentials establish current certification. This includes empty updates after the last credential is revoked or expires. Exceeding the credential validation limit also remains UNVERIFIABLE. An initial version cannot be published for a Student without approved learning evidence; an unissued Passport shell is not an issued version.

The verification RPC budget is six seconds across an issuance proof and its replacement dependency. Each transport call also has a five-second budget, one-second socket inactivity limits, an 8 MiB response limit and no redirects or transparent retries. These budgets apply between transport reads; DNS/OS scheduling can extend wall-clock time. `BlockchainRPCBudgetMiddleware` is registered in this branch's production settings and shares one budget across multiple proofs in a request. Preserve that registration during the later integration. Later records whose budget is exhausted report unavailable; they cannot reuse a saved positive badge.

Private and public root mappings are now aligned: only nested PENDING_BLOCKCHAIN produces pending; FAILED/NOT_CONFIGURED/UNAVAILABLE produce UNVERIFIABLE unless lifecycle or credential terminal status takes precedence. Private BLOCKCHAIN_VERIFIED additionally requires nested CONFIRMED and true current, signer-authorization and institutional-approval flags. Preserve these narrow shared-code corrections when resolving the later integration conflicts.

The upload verifier now calls `document_proof(document['document_id'], known_document=True)` only after `PassportDocumentRepository.find_by_hash` found the issued document. This server-only hint removes a duplicate disabled-transport existence lookup; it never bypasses enabled-chain validation and is never sourced from request parameters. The existing three-query assertion is preserved unchanged.

The target frontend at cc74833 discards unknown blockchain fields and does not accept the new pending/replaced public statuses. Its owners must update the explicit DTO allowlists, adapters and HTTP acceptance fixtures. Build explorer links only from validated chain ID 80002 and a 32-byte transaction hash using the fixed Amoy explorer origin. Label LOCAL_ANVIL as local test evidence. No private keys, provider URLs or arbitrary explorer URLs are sent to clients.

Student current/PDF reads require the existing verified linked Student session. Registrar corrections require `accounts.manage_legal_identity`; Passport revocation requires `accounts.manage_passport_lifecycle`; historical registrar reads require the registrar permission and are audited. Existing admin PDF reads retain `accounts.view_student_records` plus their existing audit rules. Session-authenticated mutations require CSRF. The public endpoints need no session or keys.
