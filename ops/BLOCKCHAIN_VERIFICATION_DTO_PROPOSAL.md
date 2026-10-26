# Future public blockchain proof DTO — proposal for Developer 2

This is coordination documentation only. This milestone does not implement a chain, change a service/model/migration/worker/key, merge an unfinished branch, or return/display a blockchain verification status. Current frontend adapters intentionally discard unknown response fields.

Before adding a public proof section, agree a backward-compatible optional DTO alongside the existing registry facts. Keep these concerns distinct:

- The exact subject: credential, Passport version or document public reference; canonicalization/digest schema version and the digest that was actually anchored. Do not hash an ambiguous mutable presentation or place student PII on-chain.
- Network/chain identifier, transaction/anchor reference, relevant block/confirmation information, and a server-assessed proof result with an assessment timestamp. An explorer URL should be built/allowlisted safely rather than treated as trusted HTML or an arbitrary redirect.
- Missing, pending, provider-unavailable and rejected proof outcomes must remain distinguishable. Absence of a proof field means “not assessed,” not “verified” and not an invented chain failure. Final enums/nullability require agreement with the implemented backend.
- Preserve registry authenticity, snapshot currency and current credential validity independently. A successful anchor must never override a revoked/expired/untrusted credential, and a historical proof must not imply the version is latest.
- Expose only public proof metadata. Signing keys, provider credentials, raw internal errors, student identity and private source payloads must never appear in public responses.

Acceptance should include independently reproducible network evidence, binding to the exact immutable issued payload/document, altered/mismatched subject/digest rejection, confirmation/reorg/provider failure handling, no proof supplied, and revoked/expired/historical registry combinations. The frontend needs an explicit adapter/test update before consuming that DTO; it will not turn a source label or unknown JSON field into a proof badge.
