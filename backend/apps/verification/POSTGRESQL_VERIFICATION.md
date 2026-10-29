# Database-backed public verification

Production defaults read real Credential and PassportDocument records. Mock
repositories remain available only through explicit injection in fixture tests.
The combined settings use `BTU-UNIVERSITY` as the fixed internal issuer. Verification
requires both the explicit trusted-reference allowlist and the linked database
issuer's `is_trusted` flag; an allowlist string alone does not confer trust. No
Passport publishing or document generation is triggered by verification.

## Credential contract and issuer approval

GET `/api/verification/<public credential UUID>/` keeps the existing response keys
and VALID, REVOKED, EXPIRED, INVALID, NOT_FOUND statuses. The source is now
POSTGRESQL_CREDENTIAL_REGISTRY. Only Credential.public_reference is accepted; User,
Student and internal Credential UUIDs are not lookup alternatives. Invalid UUID
strings safely return NOT_FOUND. Responses include no profile, evidence, grades,
internal IDs or revocation reasons.

Required Django setting: VERIFICATION_TRUSTED_ISSUER_REFERENCES, a nonempty list
or tuple of explicitly approved CredentialIssuer.reference values. The default
contains only `BTU-UNIVERSITY`. Missing,
empty, incorrectly typed, or unlisted issuer configuration fails closed to INVALID.
The immutable credential reference must match the current linked issuer, and that
issuer record must be marked trusted. A provisioned but untrusted issuer row is not
considered authentic. The database currently permits only the fixed BTU issuer to
be marked trusted.

The binding in `config.settings` is:

```python
VERIFICATION_TRUSTED_ISSUER_REFERENCES = [
    ref.strip() for ref in os.environ.get(
        'VERIFICATION_TRUSTED_ISSUER_REFERENCES', 'BTU-UNIVERSITY'
    ).split(',')
    if ref.strip()
]
```

Trust is checked before returning REVOKED, then issuance/expiry dates determine
current validity for issued credentials. No blockchain claims are produced.
PostgreSQLCredentialRepository selects only required fields in one indexed public
reference query and joins the existing issuer relation. Dependency injection and
an injectable clock remain available for deterministic unit tests.

## PDF contract and limitations to agree with Developer 1

POST `/api/verification/document/` accepts a multipart `file` without login.
It reuses Developer 1's exact PassportDocumentRepository interface, looking up the
hash of uploaded bytes and the passport's latest issued version. No filesystem
path, filename, client-provided hash, storage key, or PDF metadata is used as proof.
The response source is POSTGRESQL_DOCUMENT_REGISTRY.

- VALID: bytes match an issued registry document at the latest passport version.
- OUTDATED: registered bytes match an older issued version.
- INVALID: invalid envelope, size/type, or a repository explicitly reporting revocation.
- UNVERIFIABLE: unregistered/tampered bytes or unavailable/inconsistent version data.

The current document model/repository does NOT expose a document revocation state
or current validity of each credential represented by a historical PDF. VALID
therefore describes registered-byte integrity and version currency, not that every
represented credential remains valid. The response message states that credential
validity is checked separately. No revocation field or unsupported status was invented;
Developer 1 must agree on any richer document validity contract before rollout.

Signature/end-marker checks validate only the PDF envelope; they are not full PDF
syntax validation. An unknown file with plausible markers remains UNVERIFIABLE,
not authentic. The service deliberately does not render or parse arbitrary public
PDFs. Authoritative byte matching binds authenticity to the trusted generation path.

## Endpoint security

The two views explicitly disable session authentication and permit anonymous
verification. Invalid/expired browser sessions cannot prevent verification; the
upload action changes no Student/Credential/Passport/document data. Persistent
rate-counter updates are the only writes. Session-authenticated administrative
CSRF checks are unchanged.

The existing AuthRateLimitBucket table is reused with a distinct HMAC namespace;
no new table or migration is needed. PostgreSQL row locks enforce per-IP fixed
one-minute windows across processes: 60 credential requests and 10 PDF requests.
Counters are separate from auth budgets. Exceeded requests return 429/Retry-After.
Only REMOTE_ADDR is used; X-Forwarded-For is intentionally ignored. Configure a
trusted proxy address policy before deployment or users behind one proxy/NAT will
share the same budget. Database failure denies service; there is no unthrottled
fallback. Fixed-window boundaries can allow a short burst across adjacent windows.

File bytes are hashed with bounded 64 KiB reads, capped at 5 MiB independently of
the declared file size. A verification-specific upload handler caps aggregate file
parts during parsing; declared request bodies above 5 MiB + 64 KiB are rejected
before multipart parsing. Oversized uploads receive 413, while service-level invalid
files retain the existing verification result contract. Clients cannot bypass the
bound by lying about file size or changing filenames.

Infrastructure still MUST enforce total request-body limits (including unknown-length
and chunked bodies), multipart field/header counts, URL length, connection/read
and processing timeouts, and a global abuse limit. Recommended gateway ceiling:
6 MiB/request with bounded headers/fields and explicit request timeouts. Django's
upload handler limits file bytes, not every possible non-file multipart field.
Schedule cleanup of expired security counter rows using the accounts retention policy.
These controls are documented, not deployed or performance-certified here.

## Validation

Use the isolated local PostgreSQL harness; it never reads .env or DATABASE_URL:

```sh
cd /workspace/AI-Skills-Digital-Passport/backend
../.venv-auth/bin/python manage.py test apps.verification --settings=apps.integrations.postgres_test_settings
../.venv-auth/bin/python manage.py test apps.integrations apps.skills apps.credentials apps.passports apps.students apps.accounts apps.verification --settings=apps.integrations.postgres_test_settings
../.venv-auth/bin/python manage.py makemigrations --check --dry-run --settings=apps.integrations.postgres_test_settings
```

Tests cover valid/revoked/expired/future/untrusted credentials, public/internal ID
separation, privacy-safe responses, real generated PDFs, historical versions,
tampering/corruption, false file sizes, request limits, invalid session cookies,
shared-client and concurrent database rate enforcement. Query assertions measure
one credential query and two document lookup queries (excluding rate counters).
This is a bounded query-count observation, not a 5,000-student throughput claim.

Phase D authentication/security auditing and Phase E import reliability remain
separate work. Review Phase B's unapplied migration before shared integration;
this phase adds no migrations. No shared Neon migration, merge or deployment occurred.

## Updated integrated contract after f8057c5

The earlier integrity-only PDF limitation is superseded by the public Passport
verification work. Reference verification and registered PDF uploads now evaluate
current credential status; revoked/expired history cannot remain overall VALID.
The response adds credential_status and credential_counts and supports REVOKED /
EXPIRED, while preserving separate authentic/is_latest facts. Review the exact
precedence and empty-snapshot behavior in docs/INTEGRATION_REVIEW.md. Measured
population/query observations are in docs/PERFORMANCE.md. Database model/migration
history was not changed by this update.
