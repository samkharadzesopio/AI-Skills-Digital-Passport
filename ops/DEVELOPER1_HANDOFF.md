# Developer 1 review and remaining lifecycle work

Review branch feature/dev2-automation-verification against integration; no merge
has been performed. Developer 2 migrations: accounts/0006, integrations/0001 and
integrations/0002. Existing User/Student UUIDs and all domain models are reused.
Review table state and migration history on Neon before approving any migration.

Confirm the exact existing BTU issuer reference, public trusted-issuer allowlist,
Student active-status strings and institutional approval of Excel/Google sources.
These are now bound to environment configuration in config/settings.py. No issuer
was implicitly provisioned and no real reference was guessed.

Owned Passport lifecycle gap, observed in backend/apps/credentials/services.py and
backend/apps/passports/services.py:

- issue_credential/revoke_credential create immutable lifecycle events but do not
  invoke a reliable publication hook. on_commit alone is not durable delivery.
- Publish from durable lifecycle events and use existing PassportUpdateEvent receipts
  for deduplication/reconciliation. Do not introduce a second publishing path in imports.
- Delayed events currently pass event.occurred_at as the snapshot cutoff and can
  replace latest content with a stale snapshot. Agree on current-state refresh or
  ordering before enabling background publication.
- Expiry has no lifecycle event: schedule validity refresh at expiry boundaries.
- Distinguish credential committed, Passport published, and PDF artifact generated.
- The current document repository reports issued-byte integrity and version currency;
  it does not report revocation/current validity of represented credentials. Agree
  on the richer public semantics before claiming a PDF's included credentials are current.

Suggested acceptance tests: issuance and revocation trigger one idempotent refresh;
transaction rollback creates no published update; a lost callback is reconciled;
concurrent/reordered events never drop newer credentials from latest; expiry refresh
removes expired content; existing historical snapshots/documents remain immutable.
These changes require your ownership review; no domain/lifecycle code was silently
modified by Developer 2's rollout work. This handoff was prepared, not sent to a teammate.
