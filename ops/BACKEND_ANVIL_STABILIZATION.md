# Final backend and Anvil stabilization candidate

Date: 27 October 2026, Asia/Tbilisi. Scope: the existing Django backend and local
Anvil MVP, with no React implementation or persistent-database changes.

## A. Executive summary

The candidate incorporates the reviewed current-proof correction and additive
network metadata, adds real-domain mutation and expired-session regressions,
expands synthetic HTTP contract capture, and provides a local operator runbook.
It retains the integrated evidence/credential/Passport/PDF/blockchain services.
React integration remains a separate acceptance milestone. Public Amoy is
optional and was not deployed.

**VERIFIED for the defined local Anvil backend workflow; ready for React
integration.** The complete website remains PARTIAL until the documented
blockchain/lifecycle UI changes and real browser acceptance are completed.

## B. Git status and preserved work

- Verified starting local and fetched `origin/integration`:
  `bec0d8323ff98cb9e4e83c51f607d23d1e9ab46a`.
- Candidate: `integration-candidate/backend-anvil-stabilization`, in the new
  isolated `AI-Passport-backend-anvil-candidate` worktree.
- Reviewed and fast-forward incorporated
  `c87f801c2ffee350c93b90551e3d4fbbf5c73622`. Its parent was exactly the verified
  integration tip. The original blockchain branch was already an ancestor and
  was not merged again.
- The candidate's final commit is the commit containing this report; resolve
  it with `git rev-parse integration-candidate/backend-anvil-stabilization`.
  No merge into `integration`/`main` and no push are authorized or performed.
- All seven existing worktrees and their branches remain. The existing
  `AI-Passport-pdf-apis/ops/PASSPORT_PDF_REPORT.md` edit and both auth stashes
  remain. Existing development processes, ignored configuration, virtual
  environments, audit directories and PostgreSQL data were not adopted/removed.
- `feature/flexible-spreadsheet-integration` remains separate, as does the
  frontend developer's branch. This candidate does not silently deliver their
  additional APIs or UI changes.

## C. Blockchain correction

The final current verdict now requires the final institutional registry read
to report `VALID` and `is_latest is True`, in addition to an active identity,
correct latest pointer, nonempty valid credential support, trusted fixed BTU
issuer, authorized on-chain signer and independently checked exact commitment.
Its latest-version number is taken from that registry assessment.

The existing confirmed receipt remains historical evidence after a concurrent
version update, credential revocation, identity revocation or legal replacement;
it never preserves a positive current badge. The added tests control scheduling
only: mutations use real domain services and PostgreSQL, and the original
transaction is genuinely confirmed on native Anvil.

`network` and nullable `transaction_explorer_url` are server-derived. Only chain
80002 plus an exactly validated transaction hash yields a fixed-origin HTTPS
Amoy link. Anvil has no explorer link. Valid configuration supplies the required
confirmation minimum even before anchoring; observed confirmations remain
separate live facts. No new network, contract, wallet design or signing policy
was introduced.

## D. Django domain coverage

Reviewed and retained the canonical Student/account association; approved source
and course mappings; durable completion ingestion/verified achievements;
immutable, idempotent credential contents; credential revocation and expiration
refreshes; permanent Passport identities, immutable version snapshots and
approval-gated replacement/revocation; original BTU/Georgian PDF rendering;
registered byte-hash verification; queued PDF publication; durable signing,
nonce reservations, confirmation/reconciliation and original-byte recovery.

Student scope comes from the session, never a client Student selector. Historical
learning evidence is distinct from current valid certification. A login with no
approved evidence creates no Passport. Empty refreshes cannot regain current
verification. Cancelled identities cannot become current again. Student routes
exclude cancelled identities; permissioned audited Admin history remains usable.
No additional domain behavior was redesigned.

## E. Authentication and permissions

Existing university-email eligibility, single-use/expiring/rate-limited OTP,
Admin password login, session rotation/restoration/logout, explicit capability
checks, Student/Admin separation, cross-owner denial and CSRF protections remain.
Two new tests expire actual persisted Student/Admin sessions and prove that a
fresh client carrying the old cookie cannot restore account context/access.
Synthetic credentials are test fixtures only; no permanent user was provisioned.

The eight effective Admin capabilities remain the existing allowlist, with no
automatic grant. Generic role/staff flags or superuser access do not substitute
for the exact action permission. Public verification needs no session/signing
key and does not expose private Student names, email, evidence or file paths.

## F. PostgreSQL and migrations

Disposable PostgreSQL 18 clusters bind only loopback random ports. Test databases
are unique run-owned names, with temporary media/mail and no production `.env`.
The existing launcher rejects pre-existing databases and libpq redirection;
failure/interruption regressions check cleanup and preservation boundaries.

The candidate introduces no model/migration changes. The integrated migration
leaves remain accounts 0007, passports 0008 and blockchain 0002, alongside the
existing apps' leaves. Fresh migration application and the existing historical
schema upgrade tests cover preserved Student/Passport/version/document IDs,
frozen first-issued names/date, credential ownership, snapshot/PDF hashes/bytes,
unchanged grants, one ACTIVE identity and immutable proof/nonce guards.

Persistent local `btu_passport_local`, other developer clusters and Neon were
not queried or migrated. Their actual schema/readiness is not asserted. Exact
planning/apply commands and backup/review restrictions are in
[the local runbook](BACKEND_ANVIL_LOCAL_RUNBOOK.md) and
[the migration runbook](BACKEND_MIGRATION_RUNBOOK.md).

## G. API contract

No endpoint or permission changed. The proof metadata is additive; no migration
or client-selected network is required. Actual fresh response bodies and HTTP
status/timing/RPC observations are captured in
[BACKEND_CONTRACT_EXAMPLES.json](BACKEND_CONTRACT_EXAMPLES.json). These are
synthetic local acceptance observations, never a deployment SLA. The older
`blockchain/API_EXAMPLES.json` remains illustrative.

[BACKEND_API_HANDOFF.md](BACKEND_API_HANDOFF.md) records exact paths, nullable
and conditional fields, permissions, errors and required React parser updates.
Public `VALID`, private `BLOCKCHAIN_VERIFIED`, artifact `ISSUED`, lifecycle
`ACTIVE/REPLACED/REVOKED`, historical authenticity, currency and current support
are distinct. Pending, failed, unconfigured and unavailable are never positive.
Business verification outcomes are normally HTTP 200; invalid input/selectors
400, missing grants/CSRF 403, missing authorized content 404, conflicts 409,
template overflow 422, throttling 429 and unavailable configuration/services 503
retain their existing meanings. Invalid Admin credentials return 401.

The Student parser currently discards proof/lifecycle fields; public parsers need
`PENDING_BLOCKCHAIN`, `REPLACED`, `NOT_ISSUED` and nested proof support; auth needs
the two lifecycle grants; Admin defaults must explicitly select ACTIVE identity.
All are documented, and no React source was changed. Legacy React HTTP suites
use the existing registry-only test mode; they do not establish chain-aware UI
acceptance.

## H. Fresh validation

These results were executed during this task. Historical 559/563 totals are not
substituted for fresh evidence. The application code did not change after this
validation; subsequent edits are documentation only.

| Check | Fresh result |
| --- | --- |
| `python -B ops/run_isolated_tests.py --full` | PASS, exit 0; complete backend, cleanup boundaries, chain HTTP and all three existing React HTTP drivers |
| Nine-app Django regression within that run | **566 passed in 550.739 s**, 568 discovered; exactly two pre-existing legacy reference-SQL comparisons excluded |
| New Student/Admin persisted-session expiry tests | **2 passed in 0.454 s**, fresh separate owned PostgreSQL; added after broad-suite collection |
| Focused `apps.blockchain.test_mvp_integration` | **7 passed in 19.659 s**, including genuine Anvil confirmation and the three new domain-mutation cases; overlaps the broad suite |
| Resource cleanup tests | **6 passed**; **3 local-profile boundary tests passed**; real failure/interruption/initial-setup cleanup and existing-database refusal passed |
| Django system check and `makemigrations --check --dry-run` | PASS; no issues or migration drift |
| `npm.cmd --prefix blockchain test` | **11 passed, 0 failed, 0 skipped**, native Forge 1.7.1 / Solidity 0.8.30 |
| `npm.cmd --prefix blockchain run check` | PASS; fresh build matches complete committed ABI, creation and runtime bytecode |
| Chain-enabled `ops/test_backend_chain_e2e.py` | **11 journeys, 59 real HTTP requests**; 42 captured response examples; no API/chain responses mocked |
| `ops/test_verification_e2e.py` | PASS, **35** real proxied requests |
| `ops/test_student_e2e.py` | PASS, **64** real proxied requests |
| `ops/test_admin_e2e.py` | PASS, **143** real proxied requests |
| Frontend TypeScript/production build, lint | PASS; pre-existing >500 kB bundle warning retained |
| Frontend architecture/auth/Student/Admin/verification/demo/Passport/preview checks | PASS; preview flag supplied only to that check process, no environment file edits |
| Captured JSON/privacy review and Git whitespace | PASS; 42 synthetic responses, no forbidden credential/session/key/storage fields; no whitespace errors |

The broad suite and two later expiry tests cover **568 distinct backend tests**;
the focused seven overlap and are not added to that number. There was no new
test exclusion or weakened assertion. The existing exclusions are exactly:

- `apps.skills.tests.SkillPostgreSQLTests.test_reference_schema_matches_migration`
- `apps.students.tests.StudentPostgreSQLTests.test_reference_schema_matches_migration_and_preserves_foreign_keys`

The launcher invokes:

```text
python backend/manage.py test apps.api apps.integrations apps.skills apps.credentials apps.passports apps.students apps.accounts apps.verification apps.blockchain --settings=apps.integrations.postgres_test_settings --verbosity=1
```

The two added expiry tests were independently run with:

```text
python -B blockchain/scripts/test_backend.py apps.accounts.test_security.SessionTests.test_expired_database_session_cannot_restore_student_context apps.accounts.test_auth_api.AuthCSRFApiTests.test_expired_admin_session_does_not_restore_capabilities
```

Python 3.13.13 / Django 6.1.2 / web3 7.13.0 came from the existing isolated test
virtual environment; Node 26.3.0 and PostgreSQL 18 were used. Contract and
frontend dependencies were installed from their lockfiles only in the candidate.
The primary `.venv`, frontend dependencies and local configuration were preserved.

Raw logs are preserved outside every worktree as `backend-anvil-full.log`,
`backend-anvil-focused.log` and `backend-anvil-session-expiry.log` in the parent
workspace. They are local evidence, not tracked deployment artifacts. The full
runner verified final owned-cluster shutdown and removal; no Anvil process from
this run remains. No essential check failed in this task. Expected negative-test
logs include deliberate publication failures and 400/413/429 denials. Legacy UI
drivers emit nonfatal React `act` warnings; intentional early 429 upload rejection
can emit Vite/WSGI connection-reset diagnostics while response/cooldown assertions
pass. These are not hidden or counted as application acceptance failures.

Graphical browser, accessibility/mobile/camera, real SMTP, live Google/Classroom,
production load, persistent-schema application and public Amoy are **NOT TESTED**.
Google adapter/provider unit fixtures and transport fault injection are not
presented as live external-service acceptance.

## I. Real end-to-end journeys

All A–G journeys passed on real loopback HTTP, PostgreSQL, generated PDFs and
native Anvil. The same complete run also passed all eleven existing journeys:

| User journey | Fresh evidence |
| --- | --- |
| A: issuance | Exact-grant Excel upload → approved course mapping → achievements → credential → permanent identity/version → actual published PDF → signed/confirmed Anvil transaction → public VALID |
| B: Student access | OTP/session restoration, own dashboard/skills/achievements/credentials/current Passport/history/PDF; cross-owner credential and cancelled-version download 404; CSRF denial |
| C: public verification | Anonymous current reference/version/document proof, exact uploaded PDF; safe network/confirmation metadata, no private Student fields |
| D: revocation | Credential revocation changes old PDF validity while retaining authenticity; current refresh uses surviving valid evidence; separate permanent Passport revocation is terminal |
| E: replacement | Exact registrar grant and CSRF, approved synthetic name correction, idempotent replay, old identity REPLACED, cancellation dependency confirmed before new proof; old Admin PDF remains readable/audited |
| F: tampering | Changed PDF bytes fail registry authenticity and never inherit the original chain proof |
| G: failure recovery | Actual refused RPC connection yields UNVERIFIABLE/current false; restored same Anvil plus restarted worker commands retain exact transaction hashes/nonces and restore live verification |
| Additional 1 | Login without approved evidence creates no Passport/version; known unissued and unknown references remain NOT_ISSUED/NOT_FOUND |
| Additional 2 | Second approved completion retains permanent identity and appends an immutable version |
| Additional 3 | Role/grant/anonymous lifecycle denial, public privacy and logout invalidation |
| Additional 4 | Duplicate workbook replay creates no extra credential and cannot reactivate cancelled identity |

The chain fixture asserted four issued documents for the journey Student. The
legacy Admin fixture separately asserted six achievements, four intended
credentials, one revocation, one registered PDF, a persisted invalid-row error
and recovered durable import with no replay duplicates. Public uploads created
no new issued documents. Their databases/media/accounts were disposed.

**The previously reported dashboard HTTP 500 did not recur.** Its original
application cause remains unknown; no speculative application fix is claimed.
The c87f801 server-thread connection cleanup and sanitized diagnostics are
retained. Native Anvil recovery/confirmation/nonce concurrency, reorganization,
failed/reverted transactions, timeout boundaries and pinned-target negatives
also passed in the broader Django suite. They supplement the eleven HTTP
journeys rather than being misrepresented as additional HTTP/browser journeys.

## J. Security and compatibility review

The correction changes neither issuer approval nor authorization, CSRF, exact
chain/runtime/event/receipt/hash checks, public throttling/no-store, upload bounds
or immutable signed data. Keys/passwords are generated in disposable fixtures;
HTTP captures contain responses only and exclude OTPs, passwords, cookies,
CSRF tokens and signing material. Fixtures contain no real workbook/Student data.
Signer addresses, hashes, opaque salts and public references are public test
proof facts, not secret keys.

The whole-file pattern scan flagged eight unchanged synthetic fixture lines in
the existing account tests. Comparing normalized lines with the starting commit
confirmed they were pre-existing; added-line/new-file scanning found no new
secret pattern. The captured JSON passed a recursive forbidden-field check.
No local environment file, private workbook, mailbox, key, database file or generated
build/test artifact is included in the candidate diff.

The c87f801 HTTP driver closes thread-owned Django connections on shutdown and
captures only exception types/stack locations on unexpected server failures.
It does not expose messages, locals or request bodies, and does not suppress
failed assertions. The historical dashboard 500 has no established application
root cause; any recurrence must be investigated from fresh diagnostics.

This is focused engineering review and local regression evidence, not a formal
security certification or production durability/load assessment. Windows signer
file ACLs need operator enforcement. Original-byte recovery cannot repair an
irrecoverably underpriced or externally consumed nonce by rewriting history;
exclusive issuer operation and reviewed forward recovery remain necessary.

## K. Remaining work

1. **Backend integration:** review/authorize delivery of this candidate; review
   the separate flexible spreadsheet branch independently if required for the
   demo. Do not assume its profiles/previews/approval/skill-award APIs exist here.
2. **Frontend:** implement the precise DTO/lifecycle/proof changes above, retain
   fail-closed unknown/error states and current-only Student selection, then run
   chain-enabled graphical-browser acceptance, including replacement/revocation,
   pending/outage recovery and exact PDF uploads. No redesign is required.
3. **Local infrastructure/demo:** separately review backup/forward migrations
   for the intended demo database; provision synthetic accounts, exact grants,
   approved sources/mappings and trusted issuer; configure one matching Anvil
   registry/issuer with protected local-only keys; keep PostgreSQL, Anvil, Django,
   shared worker, signer worker and Vite running. Do not overwrite existing data.
4. **Institutional/production:** approved registrar/source policies, live Google
   service credentials or a real Classroom connector, TLS SMTP/HTTPS, backup and
   supervised operations remain outside this local acceptance. Classroom remains
   visibly simulated. General security-audit reads and controlled catalog/mapping
   writes remain separate design tasks; current read projections are preserved.
5. **Optional public chain:** Amoy authorization, custody, funds, deployment and
   independent real-network acceptance are NOT TESTED and not local MVP gates.

## L. Final readiness verdict

| Question | Verdict | Practical limit |
| --- | --- | --- |
| 1. Backend complete for defined hackathon MVP? | **VERIFIED** | Defined local Anvil backend workflow, strict approved-completion imports; complete website/institutional rollout remains PARTIAL |
| 2. Blockchain integrated with Django? | **VERIFIED** | Real PostgreSQL-backed domain/queue and native Anvil, no public deployment claim |
| 3. PostgreSQL migrations working? | **VERIFIED** | Fresh disposable schemas and preserved historical-schema upgrade fixtures; persistent target NOT TESTED |
| 4. Issuance with Anvil? | **VERIFIED** | Approved synthetic evidence, actual PDF and confirmed signed transaction |
| 5. Verification with Anvil? | **VERIFIED** | Live exact registry/runtime/receipt/event/hash/confirmations plus current institutional assessment |
| 6. Revocation and replacement? | **VERIFIED** | Immediate institutional cancellation, durable on-chain lifecycle, retained history and race regressions |
| 7. Authentication and permissions correct? | **VERIFIED** | Synthetic OTP/password/session/expiry/CSRF/ownership/exact-grant tests; live SMTP NOT TESTED |
| 8. Spreadsheet imports functioning? | **PARTIAL** | Existing strict Excel end-to-end and configured Google adapter/unit negatives pass; live Google and separate flexible branch are not integrated/tested here |
| 9. Workers operational? | **VERIFIED** | Tested isolated publication/shared/signing/reconciliation/restart/recovery; production supervision NOT TESTED |
| 10. API contracts stable for React? | **VERIFIED** | Existing routes/grants retained, additive metadata documented and actual synthetic examples captured; existing parsers still need updates |
| 11. Backend ready for real frontend integration? | **VERIFIED** | Candidate ready for review/integration; no claim of completed chain-aware website |
| 12. Website ready to demonstrate? | **PARTIAL** | Authorize candidate delivery, implement DTO/lifecycle UI handling, prepare approved consistent local DB/Anvil/account/source setup, run workers and complete graphical-browser acceptance |

No known failing backend acceptance check remains in the tested local scope.
Public Amoy is optional. The primary `integration` checkout remains unchanged;
this candidate is intentionally local, unmerged and unpushed.
