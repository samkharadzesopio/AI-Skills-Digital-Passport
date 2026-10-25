## Public Passport references and authoritative current credential validity

Baseline: integration f8057c5. Branch: feature/public-verification-integration.
No merge or schema migration is included.

Adds anonymous, PostgreSQL-backed verification of permanent Passport and exact
version public references, including the renderer's existing passport-version:<UUID>
format. Registered PDFs now check current credential revocation/expiry/trust instead
of reporting only document integrity/latest status. Authenticity and version currency
remain separate facts. Responses omit private profiles, evidence and internal IDs.

Reuses Credential.verification_status_at, existing issuer trust, immutable snapshots,
PassportDocumentRepository, public throttling and the already integrated lifecycle
outbox. No competing credential or Passport service is introduced. Public rejection
logs contain scope/status only; document queries select only required public fields.

The public PDF contract adds REVOKED/EXPIRED plus credential_status/credential_counts;
these override OUTDATED when a historical snapshot has invalid current credentials.
Consumers must handle the new statuses before integration. No historical data is
rewritten. Empty/unissued/oversized snapshots fail closed to UNVERIFIABLE.

Validation and local 5,000-student observations are in verification/docs/PERFORMANCE.md;
full implementation/status semantics are in verification/docs/INTEGRATION_REVIEW.md.
The existing test runner explicitly excludes two legacy schema-SQL comparisons;
concurrency tests run. No production throughput or live provider results are claimed.

Review client status handling, issuer policy, staging limits and institution-provided
source event identities jointly. Do not merge automatically. No shared Neon migration,
production data mutation or live deployment was performed.
