# Passport-focused Student integration

The visual source is Sopio's pushed `565d2c1522fe10b0cf32ea7571da03b86d8676c3`
(`fix/frontend-blockchain-compatibility`). The candidate starts from tested
integration `fd8c589a960cf3641792864f1453568510318c7a`. Its official brand assets,
Passport card/pagination, demo landing and Coming Soon presentation are integrated
with the existing typed Student services and complete Student/Admin route tree.
The generic replacement ProductWorkspace and its older backend assumptions are
not used. No backend, migration, contract or deployment implementation is changed.

Student navigation is My Passport, My Skills, Passport History, Skills Gap Analyzer
(Coming Soon), Public Verification and authenticated sign out. Identity is
read-only. Credential/profile/achievement/version detail URLs remain available
without adding them back to the sidebar. `/student/history` aliases the established
version list. Current and historical PDFs retain their exact backend endpoints.

Current sharing requires an ACTIVE identity, issued current version and the
backend's complete confirmed proof bound to both public references. Lifecycle,
trust, signer, network and confirmation requirements fail closed. Registry
validity and blockchain verification remain separate public facts, preserving
older registry-only deployments without inventing chain success. Pending,
replaced, revoked, unissued and historical results retain authoritative server
decisions. Admin default selection chooses an ACTIVE identity, not the first UUID.

Public verification has no sample Passport or certificate selector. Validated
credential and exact-version deep links still work. Public PDF submission retains
integration's native multipart transport, without upload-progress streaming.
Anonymous verification never bootstraps private sessions or sends login cookies.

Run `npm run build`, `npm run lint`, the existing `check:*` regression scripts,
`npm run check:integration`, and `npm run check:passport-card`. Layout checks use
an isolated Playwright installation selected by `BTU_BROWSER_TOOLS`; an existing
Chrome executable may be supplied with `BTU_BROWSER_EXECUTABLE`.

`npm run check:browser` requires `BTU_LIVE_TEST_URL` on loopback and
`BTU_LIVE_TEST_ARTIFACTS` from an owned synthetic Django/PostgreSQL/Anvil preview.
It signs in through the real UI, downloads exact PDF bytes, uploads them through
the real frontend, checks current/historical public verification and Admin routes,
checks seven live viewports, and verifies logout. It never mocks API responses or
logs passwords, OTPs or cookies. Existing ops Student/Admin/public HTTP drivers
provide additional ownership, CSRF, issuance/revocation and upload-limit coverage.
Use only newly owned disposable databases for those drivers.

The flexible spreadsheet branch is not part of this change. Existing authorized
strict import/history and explicit Google-source unavailability behavior remain.
Institutional source configuration, persistent migration rollout, workers, Amoy
and hosting remain separate operational work.
