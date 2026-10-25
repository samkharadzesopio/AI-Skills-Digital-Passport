# Joint backend integration follow-up

Developer 1's Credential-to-Passport lifecycle automation is present in the
integration candidate. Credential issuance and revocation persist durable refresh
requests, and the shared worker now polls those requests and periodically scans for
credential expirations. The combined PostgreSQL regression suite and a Classroom to
PDF verification workflow exercise this path with synthetic data.

## Remaining owner and institutional dependencies

- Provision the fixed `BTU-UNIVERSITY` issuer using the authorized management
  command before any credential issuance. Do not allow a request to choose an issuer.
- Confirm eligible Student status values, approved course-to-skill mappings, and
  whether Excel or Google Sheets are authorized evidence channels.
- Developer 2 must provide the real BTU Classroom API contract, service credentials,
  stable upstream completion event IDs, and course mapping source before live
  Classroom synchronization can replace the simulated server-owned adapter.
- Deploy `run_backend_workers` under a supervisor and monitor its retry/error states;
  no production worker or scheduler is configured by this repository change.
- Keep public PDF authenticity separate from the current validity of credentials in
  the document. The PDF verifier proves registered bytes and latest version; the
  credential verifier evaluates expiry, revocation, and issuer trust separately.
- Review and approve the additive migration plan against an isolated/staging copy
  of existing history before any shared Neon migration. No production migration was
  run during integration.

Keep domain ownership intact: imports and Classroom adapters should call the
existing Achievement, Credential, and Passport services instead of adding parallel
issuance or publication paths.
