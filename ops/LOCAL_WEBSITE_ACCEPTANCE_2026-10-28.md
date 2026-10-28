# Local website and Anvil acceptance follow-up

Baseline: `6ddd218`, `feature/passport-blockchain-proof`. The unfinished Amoy
preflight files are preserved. This work adds reproducible local test orchestration,
not another blockchain, Passport service or frontend design. No public transaction,
wallet funding, shared Neon/persistent database migration, merge or push is part
of this work.

## Reproduce

Install the existing Python requirements and locked frontend/blockchain npm
packages first. Set `PASSPORT_PG_BIN` to installed PostgreSQL binaries. On Windows
use `npm.cmd ci --ignore-scripts` for blockchain's pinned Foundry tools.

```text
python -B ops/run_isolated_tests.py --spreadsheet --ui-http --browser-http
```

`--ui-http` selects the existing backend-chain, public verification, Student
and Admin HTTP drivers without selecting the entire nine-app regression suite.
`--spreadsheet` selects the existing mapping/migration and socket-level import
checks. `--browser-http` adds `ops/test_live_browser_e2e.py`, which supplies owned
real backend/Anvil fixtures to the existing Chrome acceptance driver.
The existing `--full` behavior is retained. A full backend regression run can
still be requested explicitly with `--backend` or `--full`.

The optional graphical driver needs Playwright installed in a separate test-tool
directory (`BTU_BROWSER_TOOLS`) and a compatible Chromium executable
(`BTU_BROWSER_EXECUTABLE`, or Playwright's installed browser). These do not become
application npm dependencies. The cloud run uses `/tmp/btu-live-browser-tools`
and `/usr/bin/chromium`. PostgreSQL/Anvil/Vite/Django bind only to loopback and
use freshly allocated resources; production `.env` and existing clusters are
never adopted.

The graphical fixture reuses existing domain services, PDF publication, blockchain
workers, OTP/authentication, sessions/CSRF and the existing React driver. It
requires three actual confirmations, supplies two immutable versions, and checks
current and historical registered PDF bytes through the live interface. The
browser does not intercept API responses. Its mailbox/password are private local
fixture files, never an HTTP endpoint, and are removed with the owned run.

Only synthetic screenshots and sanitized browser result/failure JSON are copied
into the printed `/tmp/btu-live-browser-results-*` review directory. Keys, OTPs,
passwords, PDFs, media and database files are excluded. Test resources are cleaned
on normal completion and handled failure/interruption. This is disposable
acceptance, not a replacement for reviewed persistent local/staging configuration.

Additional frontend contract checks:

```text
npm --prefix frontend run check:integration
npm --prefix frontend run check:auth
npm --prefix frontend run check:student
npm --prefix frontend run check:verification
npm --prefix frontend run check:spreadsheet
```

Those smaller checks use synthetic DOM/transport fixtures. Their results are
reported separately from actual socket HTTP and real Chrome/Django/Anvil evidence.

## Scope and remaining deployment work

A passing local test does not establish public Amoy deployment, actual BTU
institutional approval, live Google Sheets/SMTP/Classroom access, or a hosted
website. The university approval in fixtures is explicitly synthetic. Public
Amoy spending remains paused and requires a funded dedicated signer, real RPC
preflight and separate explicit approval. The reported 0.01 POL is not assumed
sufficient. No Anvil key may be reused on Amoy.

The user-facing Gap Analyzer remains Coming Soon in this frontend, even though
backend course recommendation functionality exists separately. No fake AI output
or frontend action is introduced to disguise that gap.

## Fresh results

All selected gates passed; no assertion or timeout was weakened.

| Gate | Result |
|---|---|
| Frontend integration/auth/Student/verification/spreadsheet contract scripts | All five passed; synthetic DOM/transport fixtures |
| Spreadsheet PostgreSQL mapping/migration tests | All 38 passed in 53.893 seconds |
| Spreadsheet socket HTTP | 13 requests passed |
| Real HTTP/Anvil lifecycle | All 11 journeys passed, three confirmations and independent chain checks |
| Public UI/Django proxy | 35 real requests passed (jsdom) |
| Student UI/Django proxy | 67 real requests passed (jsdom) |
| Admin/Student/public UI proxy | 141 real requests passed (jsdom) |
| Real graphical Chrome | Five journey groups, seven viewports and 90 actual API responses passed; mockedResponses=false |
| Django system / migration-drift checks | No issues / no changes detected |
| Owned-resource cleanup and interruption guards | Passed; no owned cluster/private fixture directory remained |
| Source syntax / whitespace / changed-file secret-pattern review | Passed |

The actual Chrome journey covers real OTP login/session restoration, a
backend-authoritative Local Anvil proof badge, current PDF byte comparison,
current-only sharing, My Skills and read-only profile/deep links, exact historical
PDF download, anonymous current/historical reference/PDF verification with no
cookies/Authorization/CSRF headers, preserved Admin routes, navigation,
responsive views, and secure logout. It does not intercept API responses.
Direct revocation/replacement, RPC failure and nonce recovery are covered by the
separate 11-journey HTTP/Anvil suite; no additional registrar UI is claimed built.

Viewport sizes: 1440×900, 1366×768, 1280×720, 1024×768, 768×1024,
390×844 and 375×667. All four Passport sections were measured at each size;
centering, clipping, horizontal overflow, desktop visibility and mobile navigation
assertions passed. Desktop and narrow-mobile screenshots were also inspected.
The narrow-mobile capture includes a transient registered-PDF status query;
actual PDF download was verified in the browser journey before layout cycling.

Review artifacts: `/tmp/btu-live-browser-results-b21ow87e` contains only synthetic
PNG screenshots and `browser-acceptance-results.json`. Logs are
`/tmp/btu-local-integration.log` and `/tmp/btu-local-frontend-contracts.log`.
The inherited jsdom React act(...) advisories are not failures. Neither a full
nine-app backend rerun nor a persistent Windows/hosted migration is claimed.

The three existing Amoy preparation files were checked byte-for-byte against a
pre-run SHA-256 snapshot and are unchanged. The follow-up changes are only
`ops/run_isolated_tests.py`, `ops/test_live_browser_e2e.py` and this report.
They were uncommitted at reporting. The user subsequently authorized committing
and pushing these three tested follow-up files to `feature/passport-blockchain-proof`.
The existing uncommitted Amoy preparation files remain excluded from publication.
No application runtime, frontend design, existing domain service, API DTO or
migration was changed.

**Ready for repeatable disposable local website/Anvil acceptance.** Persistent
Windows demo setup, any hosted deployment, public Amoy funds/approval, live
Google access and the unfinished Gap Analyzer UI remain separate tasks. Preserve
old database/chain history and use the existing reviewed migration/registry
transition procedures; these tests do not authorize persistent database changes.
