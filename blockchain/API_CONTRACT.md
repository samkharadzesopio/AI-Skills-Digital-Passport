# Passport lifecycle contract for React, Chrome and authorized Classroom viewers

This backend feature does not copy the website or create an alternative Passport design. All clients use the same existing self-scoped Django APIs and exact stored PDF bytes. The Chrome implementation remains a separate, paused task; these are its server contracts, not a claim that an extension has been implemented.

## Current student Passport

`GET /api/student/passport/` requires the existing active verified linked Student session. It accepts no Student selector. The existing object shape is retained, adding `lifecycle_status`, `first_issued_at` and `blockchain`.

- `{"passport": null}` means no active identity. Never fall back to a cancelled Passport cached by the client.
- `lifecycle_status` is ACTIVE, REPLACED or REVOKED. This student endpoint only returns ACTIVE identities; cancellation history is admin-only.
- Root `status` is NOT_ISSUED, PENDING_BLOCKCHAIN, UNVERIFIABLE or BLOCKCHAIN_VERIFIED in the production enforcement policy, with REVOKED/EXPIRED/INVALID taking precedence when represented credentials lose validity. Database snapshot `latest_version.status=ISSUED` by itself is **not** a blockchain verification result.
- Only show the BLOCKCHAIN VERIFIED label if root status is BLOCKCHAIN_VERIFIED and both `blockchain.blockchain_verified` and `blockchain.institutional_identity_verified` are true.
- `public_reference` is the permanent public Passport identity. `latest_version.public_reference` is a separate public version identity. The internal UUID `id` and Student UUID are not verification codes.

Legal replacement changes both public identities, the PDF and its proof. The Student UUID and academic records remain stable. Discard the old Passport cache on replacement/focus/reconnect and refetch the current endpoint. Do not choose a Passport by a client-supplied Student ID or keep an old identity as current during a retry.

## PDF APIs

Existing routes are unchanged:

- POST `/api/student/passport/pdf/` with `{}`: idempotent generation, existing session CSRF required.
- GET `/api/student/passport/pdf/status/`: metadata/status.
- GET `/api/student/passport/pdf/download/`: exact private generated PDF bytes.
- Version-specific routes under `/api/student/passport/versions/<internal version UUID>/pdf/...`: only versions of the current ACTIVE identity are available to Students.

Metadata adds `blockchain`, separate from the PDF artifact's own status/availability. A downloadable issued PDF can still be pending blockchain or issuer approval. Show that pending/error state explicitly. Never call it blockchain-verified based on `available_for_download=true` or document status ISSUED.

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
| VALID | Current identity/version, currently valid credentials (when present), actual independently validated chain commitment and approved BTU HTTPS registry declaration |
| OUTDATED | Authentic earlier version of an active identity; do not present as the latest Passport |
| REPLACED | Identity cancelled for approved replacement; never current/valid, even if its old chain record remains authentic |
| REVOKED | Institution or registry explicitly invalidated the identity/represented credential |
| EXPIRED / INVALID | Existing credential-related invalidity, or integrity/trust invalidity |
| PENDING_BLOCKCHAIN | No trustworthy confirmed commitment yet; includes explicit nested operation failure needing recovery |
| UNVERIFIABLE | Chain/authority/integrity cannot be established; never render a positive badge |
| NOT_FOUND | Unknown public reference |

`authentic=true` is historical registered-document authenticity, not a current-validity badge. `is_latest` describes version currency. A replaced identity always has `is_latest=false` even though its immutable internal last-version pointer remains for audit.

The chain object uses:

- `status`: NOT_CONFIGURED, PENDING_BLOCKCHAIN, FAILED, CONFIRMED, UNVERIFIABLE, UNAVAILABLE or NOT_FOUND.
- `blockchain_verified`: live-confirmed, currently ACTIVE identity and latest-version commitment with currently valid represented credentials. It is false for cancelled identities and revoked/expired/invalid credentials, including while snapshot refresh is pending.
- `registry_status` and `credential_status`: current institutional checks, when available after independent chain verification. A historical confirmation does not override credential revocation.
- `historical_blockchain_authentic`: independent proof of the original on-chain commitment; can remain true after replacement/revocation.
- `institutional_identity_verified`: validates BTU's live HTTPS declaration for this chain, registry and runtime code hash. A database issuer boolean is insufficient.
- `issuer_key_authorized`: the pinned access-controlled registry accepted this signer at issuance; later issuer-key rotation does not rewrite that history.
- `environment`: LOCAL_ANVIL or POLYGON_AMOY. Never display Anvil data as a public Amoy deployment.
- When available: chain_id, contract_address, issuer_address, transaction_hash, block_number, block_hash, confirmations, onchain_status, opaque keys, commitment, commitment_salt, pdf_sha256 and snapshot_sha256.
- `replacement_transaction_hash`: confirmed old-key cancellation dependency for a replacement PDF.
- `error` and `retryable`: bounded classifications; no raw provider errors, signing data, storage paths or private keys.

REPLACED/REVOKED are authoritative immediately after institutional cancellation, even while its on-chain cancellation is pending. `onchain_status` honestly reports the separately observed contract state. No former legal name or successor's public reference is disclosed by the old public lookup.

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
python blockchain/scripts/verify_transaction.py --rpc-url APPROVED_HTTPS_AMOY_RPC --chain-id 80002 --registry-address ACTUAL_REGISTRY --proof-json proof.json --pdf passport.pdf --confirmations 3 --issuer-identity-url ACTUAL_BTU_HTTPS_DECLARATION
```

The tool has no PostgreSQL access or signing key. It recomputes the salted PDF/snapshot commitment and checks the pinned contract, signer, exact input, event, canonical receipt, confirmations, current contract lifecycle and any replacement dependency. It validates institutional root publication separately. A transaction hash alone proves neither the contents of an arbitrary PDF nor current institutional status.

The tool intentionally reports `institutional_current_status=NOT_CHECKED`: on-chain integrity alone cannot establish a still-pending institutional cancellation. Combine the independent chain check with the authoritative public BTU lifecycle API. It never emits a blanket VALID/MVP-complete result.
