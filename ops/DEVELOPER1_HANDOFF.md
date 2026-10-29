# Joint integration review — public verification

Current baseline integration f8057c5 already includes Developer 1's trusted fixed
BTU issuer provisioning, lifecycle outbox, bounded retry delivery, expiry refresh,
current-state Passport publication, snapshot/document immutability and worker hooks.
The older c64d4a2 lifecycle gap list is superseded; those features were inspected
and reused, not reimplemented on this branch.

Review feature/public-verification-integration against f8057c5. No schema migration
is added. The code reads existing Passport/Version public references, including the
renderer's `passport-version:<UUID>` format, and evaluates each snapshot's current
Credential status through the domain verification method and trusted issuer policy.

The important API change: a registered old PDF containing a revoked/expired
credential reports REVOKED/EXPIRED, not merely OUTDATED. Registered-byte authenticity
and latest-version currency remain separate fields. New public reference routes
return aggregate credential status/counts without private Student data. Review UI
handling for these statuses; never show overall validity solely from authentic=true.

The only Passport application changes are minimal document-repository field
projection and the regression expectation for a revoked historical PDF. No domain
model, issuer provisioning, lifecycle function or migration was changed.

Joint acceptance: revoked/expired references and PDFs fail current validity even
while refresh is pending; once refreshed, historical artifacts remain immutable;
unknown/private IDs never resolve as public references; no login is required for
verification; existing Student/Admin ownership remains protected. The combined
suite and local measurements are documented in:
backend/apps/verification/docs/INTEGRATION_REVIEW.md and docs/PERFORMANCE.md.

No shared Neon migration, production data mutation or merge was performed. Live
BTU/Google/SMTP connectivity, actual staging load and source event alias policy
still require institution/deployment coordination. This handoff is prepared in the
repository; no message was sent to another developer.
