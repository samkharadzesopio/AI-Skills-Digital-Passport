# Frontend compatibility fixes before blockchain integration

Date: 2026-10-27.

## Branch safety and inspected contracts

Work is on `fix/frontend-blockchain-compatibility`, created from the verified current frontend HEAD `6b5bd0ba69d4d7a1481ad3ffeb2c20e4001067dc`. All existing staged and uncommitted product-integration changes were carried forward without unstaging or replacing them. The initial network-restricted fetch failed; the authorized fetch outside that restriction succeeded. Remote refs remained at integration `cc74833` and blockchain feature `c8cc9fd`. No branch was merged or pushed, no other worktree was edited, and no backend code or migrations were modified.

The frontend preserves compatibility with the integration registry APIs. The blockchain feature branch was inspected read-only: private `PassportSerializer`, current-passport selection, public passport serializers/service, and `document_proof`/`version_proof` implementation. It is provisional evidence, not an agreed final contract.

## Bugs and fixes

- Passport actions previously checked only `latest_version.status`. An inactive parent could therefore retain current sharing and PDF controls. Parent `status`/`lifecycle_status` now takes precedence for presentation and action eligibility. Unknown states never activate a passport.
- No history journey existed. Students can now inspect the confirmed paginated version endpoint, verify a specific historical reference, and download an existing version-specific PDF. Historical records are explicitly labeled and never promoted to current, even if their nested state is `ISSUED`. Historical PDF generation has no dead button.
- Legal-name replacement could be confused with version recency. Current selection remains exclusively the backend current-passport response. React does not compare names, rank passports, manufacture replacements, or select a current identity from history. Inactive records are shown as inactive; pending replacements are not labeled current/valid.
- Current student PDF operations use the returned immutable version UUID when available, avoiding implicit-latest drift. Current records refresh on focus, after relevant mutations, manually, and at a 15-second interval. While revalidating a current resource, cached action controls are hidden. This reduces stale presentation; it cannot replace atomic backend lifecycle enforcement.
- A browser without Clipboard API support previously threw synchronously. Sharing now catches both absent API and rejected writes and provides a select/copy fallback.
- Admin navigation and route content previously ignored read capabilities. Navigation is filtered, direct unauthorized routes show a permission message, and protected content does not mount or request data. Invalid student UUID routes do not issue requests. Django remains the final authorization boundary.
- Repeated credential forms previously reused the same label/input ID. IDs now incorporate the credential UUID.
- Live caches could survive an externally changed account or capability set. Session revalidation now cancels and removes live queries before publishing a changed session. Existing logout, restoration, CSRF rotation and Demo Mode boundaries remain in place.
- Import feedback could crash on malformed nested responses and omitted validation failures. Shared response parsing now validates nested passport/import objects; import feedback reports returned validation-error counts. Issuance and revocation check their returned credential identity/status before reporting completion or refreshing records.
- Public parsing rejected inactive latest snapshots when `is_latest=false` but numeric versions matched. This is a real lifecycle response on the inspected branch; it now preserves revoked/replaced status. Active `VALID` and ordinary `OUTDATED` consistency checks remain strict.
- Public verification remains passport/PDF-only. `REPLACED` and `PENDING_BLOCKCHAIN` are supported from the inspected passport serializer. Failure comes from the observed nested proof status, not an invented top-level `FAILED` contract. Unsupported top-level statuses still fail closed.

## Blockchain dependency isolation

`src/verification/blockchain.ts` consumes only observed non-success status information. It outputs `missing`, `pending`, `failed`, `unverifiable`, or `unavailable`. It never outputs a verified state or exposes raw proof objects, hashes, addresses, provider errors, or student data.

A legacy integration response without a blockchain field may still display its approved **registry** validity; it explicitly makes no blockchain success claim. A proof-bearing `VALID` response with pending/failed/unavailable/malformed evidence cannot display the green valid result. Explicit null proof is unavailable, not legacy omission. Even provisional `CONFIRMED` remains unavailable for success until the final policy is agreed.

Private lifecycle presentation similarly does not activate a modern proof-dependent replacement from a status string alone. A backend-selected legacy registry `ISSUED` passport remains usable. An explicitly active pending record may prepare its PDF, because document anchoring depends on PDF creation, but it is not offered as a current-valid shared passport. Current-valid activation for the new blockchain contract is intentionally not implemented yet.

Backend confirmation is required for:

1. Final required proof fields and exact success predicate, including issuer approval, reference binding, chain/environment, confirmation freshness, and current versus historical authenticity.
2. Lifecycle status vocabulary, replacement/current-selection guarantees, and the meaning of `is_latest` for inactive records.
3. PDF preparation/download permissions during pending confirmation, after revocation, and for replaced historical passports.
4. Source/versioning policy distinguishing registry-only deployments from mandatory blockchain verification; no implicit downgrade should be possible.
5. Final pending, failed, unavailable, expired and revoked response semantics across both reference and PDF verification endpoints. The inspected document and passport serializers are not assumed to be identical.

No chain calls, wallet operations, lifecycle writes, name-change endpoint, or invented backend routes were added. Credential verification backend security is untouched. Classroom remains explicitly simulated/preview-only in this frontend; institutional synchronization and the planned Chrome integration remain in scope for the owning developer.

## Files changed in this fix

- `src/live/passport.ts`: lifecycle presentation/action guards.
- `src/live/ProductWorkspace.tsx`: current/history views, version-bound PDF controls, refresh behavior, clipboard fallback, admin gates, mutation/import feedback, form IDs.
- `src/auth/hooks.ts`: clear live cache on session identity/capability changes.
- `src/services/product.ts`: reusable parsing and nested passport validation.
- `src/verification/blockchain.ts`, `contracts.ts`, `service.ts`, `pages.tsx`, `i18n.ts`: isolated proof availability, lifecycle statuses, privacy-preserving result presentation. New Georgian-locale status strings currently fall back to English pending translation review.
- `scripts/check-product.mjs`, `scripts/check-compatibility.mjs`, `package.json`: regression coverage and check command.
- This report. Earlier staged product-integration files remain preserved separately in the index.

## Test evidence and limits

Build, lint, and all ten available regression commands passed: `check:architecture`, `check:admin`, `check:verification`, `check:demo`, `check:preview`, `check:passport`, `check:auth`, `check:product`, `check:public-transport`, `check:compatibility`. `git diff --check` also passed after removing a trailing space.

New coverage exercises inactive-parent overrides, current/history separation, backend-returned replacement states, pending PDF preparation without activation, unknown/malformed proof, explicit null proof, provisional confirmation without success, public privacy, same-number inactive snapshots, clipboard fallback, historical reference/download paths, capability-denied routes, malformed student identifiers, and session identity changes. Existing restoration/logout, OTP/CSRF, network, no-passport, import failure and Demo Mode tests are retained.

These are synthetic contracts, jsdom flows, and disposable HTTP fixtures. They do not establish real Django/PostgreSQL/Polygon integration, live name replacement, real SMTP, or graphical browser validation. The earlier local audit found no available Python environment/backend configuration and no running Django service; this task does not provision them. The production build retains its existing large-chunk warning. Real service acceptance against the finalized backend remains an integration blocker.
