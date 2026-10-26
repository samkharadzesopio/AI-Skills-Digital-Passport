# Admin portal integration — 26 October 2026

The primary `AI-Skills-Digital-Passport` checkout on `integration` now provides a live Admin workspace over Django and PostgreSQL. It completes the synthetic university → Student → public verification acceptance journey. This is local acceptance using real APIs and persisted test records, not institutional approval or production deployment.

## Authorization and sessions

The existing login and `/api/accounts/me/` summaries retain their fields and add `capabilities`. Students receive `[]`. Administrators receive only effective grants from this explicit allowlist: `view_student_records`, `manage_student_accounts`, `manage_credentials`, `revoke_credentials`, `sync_classroom`, `import_completions`.

`apps/accounts/authorization.py::admin_capabilities` delegates every capability to the unchanged `has_admin_permission(user, 'accounts.<name>')`. This preserves active/verified Admin requirements, explicit Django user/group grants, staff consistency and superuser rejection. Role, staff status or a generic `access_admin_api` grant alone never unlock a feature. Unknown capability strings are discarded by the frontend; absent capabilities fail closed.

Read pages and evidence selection require `view_student_records`. Student writes additionally require `manage_student_accounts`; issuance requires `manage_credentials`; revocation separately requires `revoke_credentials`. Classroom and import pages require their own grants and work without the records grant. Administrators holding a write grant without the records grant cannot browse private records through this UI. Frontend gates control visibility only: every backend endpoint still independently enforces its existing exact grant.

Sessions, password login, Student OTP, logout and CSRF use the existing shared services. Account-scoped private queries are cancellable, have no persistent cache, revalidate on navigation/focus/reconnect and clear through the existing logout behavior. HTTP 401/403 triggers session revalidation; expired sessions return to login. Safe error messages discard provider text, source payloads and authentication diagnostics. Retry-After is enforced without automatically replaying writes.

## Routes and actual endpoints

All API paths below are prefixed `/api/`. Numbered lists use Django page pagination; histories use bounded cursor pagination. The client reconstructs fixed same-origin paths and only extracts cursor tokens, never follows server-supplied URLs.

| Admin route | Endpoint and behavior |
|---|---|
| `/admin/login` | Existing `accounts/csrf/`, `accounts/login/`, `accounts/me/`, `accounts/logout/`; password session with effective capabilities |
| `/admin/dashboard` | GET `admin/statistics/`; actual Student, unique recognized skill, achievement, credential-validity and Passport counts; no invented trends |
| `/admin/students` | GET `admin/students/?search=&program=&education_level=&student_status=&page=`; real filters/pagination; POST `admin/students/` for authorized creation |
| `/admin/students/:id` | GET `admin/students/{uuid}/`; PATCH the same route for program/education/status only; paginated GET `admin/students/{uuid}/achievements/` for verified evidence |
| `/admin/credentials` | GET `admin/credentials/?student_id=&status=&page=`; actual validity and issuance states |
| `/admin/credentials/:id` | GET `admin/credentials/{uuid}/`; POST `admin/credentials/{uuid}/revoke/`; GET `admin/credentials/{uuid}/history/` for persisted lifecycle events |
| `/admin/students/:id/passport`, `/admin/passports/preview` | GET `admin/passports/?student_id=&page=`, GET `admin/passports/{uuid}/versions/?page=`; actual current/historical snapshots |
| Passport PDF controls | POST `admin/passports/{uuid}/pdf/?version_id={uuid}` with `{}`; GET `pdf/status/` and `pdf/download/` with the same version selector |
| `/admin/classroom-sync` | GET `integrations/classroom/completions/`; POST `classroom/sync/` with only `dry_run`; GET `classroom/events/?cursor=`; POST `classroom/events/{uuid}/retry/` with `{}` |
| `/admin/imports` | POST multipart `integrations/import/excel/`; POST `import/google-sheets/` with `{}`; GET `imports/?cursor=` and `imports/{run_id}/events/?cursor=`; POST `imports/events/{uuid}/retry/` with `{}` |
| `/admin/skills` | GET `admin/catalog/?page=`; read-only persisted skills, category and one subcategory |
| `/admin/course-mappings` | GET `admin/course-mappings/`; read-only projection of the same approved repository used by recognition |
| `/admin/audit-logs` | Truthful history hub linking credential lifecycle and independently permissioned sync/import histories; general security-audit reading is explicitly unavailable |

`frontend/src/admin/live/contracts.ts` validates runtime DTOs and projects only the fields needed by these views. Existing Student snapshot/PDF parsers and the issued preview adapter are reused. Loading, empty, malformed-response, missing-grant and network-error states never substitute demo records. The original demo pages remain behind the separate development-only Demo Mode; their local edits and disabled action stubs never run as live management.

## Student records, evidence and credentials

Student creation writes a canonical Student record; it neither creates a login account nor invites/links an existing identity. Academic edits send only `program`, `education_level`, `student_status`. University ID, name and email remain protected by the existing serializer/identity policies. The existing approved account invitation process is separate.

Credential issuance is on the Student detail page. It selects persisted `VERIFIED` achievement UUIDs, displays previous credential associations, accepts optional expiration and sends only `achievement_ids`, `idempotency_key`, `expires_at`. Backend eligibility is rechecked under its existing locks. No arbitrary title, skill claim, issuer or Student selector is sent. Learning-format stamps are not assessed proficiency. The same request key is retained during retries until selection/expiration changes; replay returns the same credential. Deliberately issuing a separate credential is not treated as new learning evidence.

Sensitive writes require an explicit review/confirmation. Revocation sends an actual credential UUID and nonempty bounded reason under its separate grant. Mutation success refreshes affected live Admin and mounted Student queries. Public verification is independently resubmitted; no result is locally manufactured. The real acceptance test observes Student and public revoked states after the Admin write.

Passport preview uses actual immutable issued snapshots, public references and current/historical identity facts from the existing APIs. Existing PDF documents are reused. PENDING/GENERATING status is polled without repeated POSTs. Generation requires `manage_credentials`; status/download require `view_student_records`. Downloads validate PDF bytes/content type and the backend's fixed filename, keep blobs out of query/storage state, and revoke object URLs. Original BTU templates and Georgian rendering are unchanged. No signature, authenticity verdict or chain proof is inferred from issuance/artwork.

## Controlled integrations and history

Classroom is visibly **SIMULATED**. Preview displays the actual controlled adapter records, grade/pass/date and completion status. Dry-run and sync submit only `dry_run`; events are server-sourced. Sync can automatically award achievements and issue credentials under its existing authorized pipeline. Persisted history shows state, attempts and sanitized errors. Retry submits no replacement payload and is offered for failed retryable events within the attempt bound.

Excel selects a nonempty `.xlsx` up to 5 MiB, checks completion headers/row limits locally and uploads actual multipart bytes. The required schema is `external_student_id, course_id, completion_status, grade, passed, completion_date, source_event_id`. Django remains authoritative for the workbook active sheet, values, source approval, course mapping and duplicate detection; valid rows may commit even when others fail. Safe row-level results and persisted sanitized errors are displayed. Run-event reads supply actual IDs for the existing retry endpoint. After replay, the existing `reconcile_run` service updates derived import history from persisted outcomes, retaining validation errors.

Google Sheets sends no URL or source selector. Only the configured approved server source can be read. Missing sheet/source/credentials produce a truthful configuration/unavailable message; provider internals are never displayed. No live Google credentials or university connection were configured or exercised.

Catalog and mapping management remain read-only. There are no frontend approval controls masquerading as policy writes. Recursive classification, versioned catalog/mapping writes and their approval process still need a separate institutional design. General security audit access needs a dedicated read grant and sanitized API; the broad Student-record grant is not repurposed to expose authentication logs. Credential history excludes actor identity, IP digests, free-text reasons and source payloads.

## Backend changes

- Allowlisted effective capabilities added to the existing account summary; no authentication or permission rule replaced.
- Four read-only Admin projections: verified Student achievements with association counts, skill catalog, approved mappings and credential lifecycle history. All require the existing records grant.
- Bounded import-run event read under `import_completions`; retry uses existing reconciliation to refresh derived run state.
- Focused authorization/contract tests and the disposable real HTTP harness.

**No migrations, models, credential/Passport domain services, PDF templates/renderers, public verification contracts, production settings, external dependencies, workers or blockchain files changed.** No Neon/shared/production database was touched. Local environment files, mailboxes and virtual environments were preserved.

## Fresh validation

| Check | Result |
|---|---|
| Full combined Django regression, including guarded local profile, accounts, Student/API security, credentials, Passports/PDFs, skills, integrations and verification | **472 passed in 199.198 seconds**; 474 discovered, the same two pre-existing legacy reference-SQL comparisons explicitly excluded by the existing runner |
| Django system check, migration drift and Git whitespace | PASS; no model migration required |
| TypeScript/production build, lint | PASS; existing bundle-size warning remains |
| `check:admin` | PASS; retained demo invariants plus live grant combinations, DTO/DOM states, safe issuance/retry/revocation, sync/import history, configured Sheet failure, empty/malformed/offline results, cursor origin isolation, rate-limit cooldown, CSRF and mid-page session expiry |
| `check:auth`, `check:student`, `check:verification`, `check:architecture`, `check:demo`, `check:passport` | PASS |
| `check:preview` | PASS with demo flag supplied only to that process; ignored configuration unchanged |
| `ops/test_admin_e2e.py` | PASS: **144 real proxied requests** through React → Vite → Django → disposable PostgreSQL, with no API responses mocked |
| Existing Student HTTP regression | PASS: **62 real proxied requests**, real OTP/session/PDF/ownership/CSRF coverage |
| Existing public verification HTTP regression | PASS: **35 real proxied requests**, real references/PDFs/lifecycle facts and rate-limit behavior |

Admin acceptance signs in a synthetic explicitly granted administrator, creates/edits a Student with identity-update rejection, previews/syncs the existing simulation, sees verified achievements, issues/replays an evidence-based credential, generates/downloads the registered PDF, submits it through public React verification, revokes through Admin, and signs in through the real Student OTP form to observe the new state. It then verifies the same PDF publicly as authentic with revoked support. It uploads a real workbook with valid/invalid rows, inspects history, recovers a durably received failed event, replays it without duplicate issuance, and observes unavailable Google configuration. Read-only Admin, Student, missing-CSRF and expired-session denials are checked.

PostgreSQL assertions confirm six achievements, exactly four intended credentials (sync, explicit issuance, Excel and recovered event), one revocation, one issued PDF and a persisted row error. All fixtures and generated acceptance artifacts are discarded by the harness. No permanent local administrator or university evidence was invented.

The drivers use jsdom for actual React rendering and real HTTP; they do not certify a graphical browser, mobile/keyboard accessibility, camera scanning or the OS file-save dialog. Nonfatal React `act` scheduling diagnostics occur around real asynchronous requests. The existing public throttle test can emit WSGI/Vite connection-reset diagnostics for an intentional early 429; the expected response and cooldown still pass. An initial Admin harness attempt used the wrong existing upload element ID; fixing the test selector allowed the full journey to pass without an application verification change.

## Reproduce and local use

From the primary repository, use the existing virtual environment and isolated loopback PostgreSQL documented in `STUDENT_INTEGRATION.md`:

```powershell
$env:FOUNDATION_TEST_PG_HOST='127.0.0.1'
$env:FOUNDATION_TEST_PG_PORT='55435'
$env:FOUNDATION_TEST_PG_PASSWORD='local-test-unused'
$env:AUTH_TEST_PG_PORT='55435'
.\.venv\Scripts\python.exe ops/test_admin_e2e.py
```

The harness never imports production `.env`; it uses production URL routing with safe test settings, an isolated test database and ephemeral Django/Vite ports. It exposes no fixture/OTP/control API.

For normal local use, keep Demo Mode off and start the existing guarded profile with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ops/start_local.ps1`. Open `http://127.0.0.1:5173/admin/login`; Student and public entry points remain `/student/login` and `/verify`. An actually provisioned Admin password account and exact grants are required. The existing `bootstrap_admin` command prompts for a password and accepts explicit approved permission codenames; use the established institutional/local provisioning process rather than editing roles in the browser. Trusted issuer, source approval, Sheet credentials and worker operation remain existing operator responsibilities. Missing dependencies are shown truthfully; this milestone does not configure external credentials.

## Preservation and remaining scope

Work remained on the existing primary `integration` branch. No branch, worktree or clone was created, deleted, reset or force-pushed. All other worktrees, two stashes and the pre-existing PDF-report edit are preserved. `main` is unchanged. Environment secrets were neither printed nor committed.

`origin/feature/passport-blockchain-proof` at `044264f` was found and inspected read-only. It remains separate. Its proposed Passport lifecycle changes, additional registrar/lifecycle grants, statuses and nested chain facts require a coordinated contract review and fresh regression testing before a future integration. This Admin milestone neither imports those capabilities nor claims to assess chain proof. No Developer 2 code or branch was merged/modified.

Remaining work includes approved catalog/mapping administration, a dedicated security-audit read policy, institution-approved sources/issuer, live Classroom/Google operation where authorized, complete Georgian UI translations, graphical/accessibility acceptance and deployment operations. Existing recommendation, blockchain and Neon work remain separate. Stop here: this milestone does not start deployment, blockchain integration or unrelated features.
