# Critical frontend fixes — 2026-10-28

Verdict: **NOT READY TO MERGE**. Frontend regression checks pass, but real-service acceptance and current remote conflict review remain outstanding.

## Completed changes in this pass

- `src/App.tsx`: removed demo student credentials, settings, and playground routes; old demo passport route redirects to the passport landing. Administrator routes remain intact and protected.
- `src/layouts/StudentLayout.tsx`: reduced navigation to My Passport, Skills, Skills Gap Analyzer, and public verification. Removed student links to administrator and editable profile pages, and the promotional sidebar widget.
- `src/pages.tsx`: replaced the demo greeting, statistics, charts, and recent-credential widgets with the passport card and clearly unavailable demo actions. Removed the profile editing/localStorage form. Analyzer displays Coming Soon without recommendations or input controls.
- `src/live/ProductWorkspace.tsx`: live landing reads the actual self-scoped dashboard/profile and passport endpoints. Added a separate history route using the existing versions endpoint; removed student credential/profile navigation. Sharing, PDF preparation/download, reference verification, and history retain real adapters. Unavailable PDF and sharing states explain the dependency. Record metadata and proof details are expandable. Session email remains visible. Background refresh preserves loaded content instead of replacing it with a loading screen.
- `src/live/product.css`, `src/artwork-theme.css`, `src/components/PassportCard.tsx`: compact passport display and responsive landing styles, preserving BTU assets, paginated content, keyboard/touch controls, and the readable text alternative. Compact display styling was adapted from locally available commit `adb4dee`; no branch was merged or checked out.
- `src/verification/pages.tsx`: removed the fictional public passport preview and updated the introduction to focus on reference/PDF verification. No certificate selector was added.
- `scripts/check-auth.mjs`, `scripts/check-preview.mjs`, `scripts/check-product.mjs`, `scripts/check-passport-layout.mjs`: updated expectations for the landing, removed routes, sharing label, separate history, and preview-free public verification. Added 1440 × 900 coverage.

These changes extend substantial work that was already staged, unstaged, and untracked. Existing API, authentication, blockchain, artwork, and test changes outside this list are not attributed to this pass. The index was not changed. Copies of the seven initially edited source files were retained under a uniquely named `btu-critical-fixes-baseline-*` directory in the execution user's temporary directory.

## Functionality and integration boundaries

Public PDF submission already uses multipart `file` at `POST /api/verification/document/`; reference lookup uses the documented passport/passport-version endpoints. Existing file limits, PDF header validation, timeouts, cancellation, cookie-free transport, source allowlisting, status parsing, and failure handling were preserved. No positive verification is generated locally. Revoked, expired, invalid, missing, outdated, pending, and unverifiable states retain their existing semantics.

Public verification requires Live Mode, `VITE_PUBLIC_VERIFICATION_ENABLED=true`, and a confirmed non-simulated source allowlist. It remains intentionally unavailable without those deployment prerequisites. The local `.env.local` selects Demo Mode, which never submits real verification/authentication requests. Production build disables Demo Mode.

Student OTP login, administrator password login, restoration, CSRF rotation, logout, protected routes, role boundaries, and capability checks retain their existing implementations. Removing a navigation link does not grant or revoke backend permission; Django remains authoritative. Students cannot enter live administrator pages through a role change in navigation. Demo Mode is explicitly an unauthenticated sample workspace.

Live PDF download requires backend readiness and a PDF binary. Share links require confirmed current validity under the existing adapter. A record with newer blockchain fields may remain unshareable pending proof-contract confirmation; this pass does not loosen that restriction. Proof data is not presented as confirmed blockchain verification.

Administrator credential management and imports remain present. Backend credential records, proof data, history, and all backend/blockchain code were untouched.

## Testing evidence

Executed from `frontend`:

- `npm.cmd run build`: PASS, including `tsc -b` and production bundling. Main bundle approximately 731 kB; Vite reports its existing large-chunk warning.
- `npm.cmd run lint`: PASS.
- `npm.cmd run check:architecture`: PASS.
- `npm.cmd run check:admin`: PASS.
- `npm.cmd run check:verification`: PASS, including validation/status/error contracts.
- `npm.cmd run check:demo`: PASS.
- `npm.cmd run check:preview`: PASS after updating obsolete route/dashboard expectations.
- `npm.cmd run check:passport`: PASS.
- `npm.cmd run check:auth`: PASS after supplying the existing no-passport response for the new landing request.
- `npm.cmd run check:product`: PASS after updating sharing/history assertions; rerun after final live UI changes.
- `npm.cmd run check:public-transport`: PASS using a disposable HTTP fixture, including multipart upload and HTTP failures.
- `npm.cmd run check:compatibility`: PASS.
- `npm.cmd run check:passport-card`: PASS.
- `npm.cmd run check:passport-layout`: PASS in headless Chromium at 1366 × 768, 1440 × 900, 1920 × 1080, 1024 × 768, 768 × 1024, 390 × 844, and 375 × 667. Exercises demo landing, absence of public preview, keyboard/touch controls, readable text, and 33 synthetic variable-content pages. No clipping/internal-scroll failures reported. Desktop screenshot visually inspected.
- `git diff --check`: PASS; only Git line-ending warnings.
- `Test-NetConnection 127.0.0.1 -Port 8000 -InformationLevel Quiet`: FALSE.

Initial test runs failed because they expected removed analytics/settings, the old sharing label, history inline with the current passport, or the public sample card. Those assertions were adapted and rerun. An initial browser selector expected “Upload” but the actual translated label differed; it now selects the upload route. Concurrent test attempts also reported Vite HMR port contention. Final focused reruns passed.

Authentication/product tests use synthetic Axios responses and jsdom. Public transport uses a fixture HTTP server. Browser layout tests use Demo Mode and synthetic records, not Django accounts. No real PostgreSQL, OTP delivery, PDF generation/storage, import, revocation, or blockchain end-to-end journey was executed. Browser checks do not establish live workspace visual acceptance; that requires a working backend and issued record.

## Git handoff

- Branch: `fix/frontend-blockchain-compatibility`.
- Latest commit: `6b5bd0b` — `feat: integrate Django session authentication and login flows`.
- Many staged, unstaged, and untracked files existed before this request and remain preserved. Changes from this pass are uncommitted. No reset, stash, checkout, merge, commit, or push was performed.
- `git fetch --all` attempted with a command-scoped safe-directory exception; failed to connect to GitHub port 443. No global Git configuration was changed.
- Current branch has no configured upstream in the local branch listing. Locally cached `origin/integration` is `fd8c589`; local `integration` is 34 commits behind that cached reference. These are snapshots, not a fresh remote synchronization claim.
- Relevant cached frontend branches include `feature/frontend-passport-ux-stabilized`, `feature/passport-first-landing-verification`, and `feature/frontend-backend-final-integration`. Backend integration/proof candidates also exist locally.
- No unresolved conflict entries are present. Substantial overlap exists in frontend routing, workspace, card, theme, verification, and test files across those branches. A clean merge cannot be promised without fetching and reviewing the final combined diff.

## Remaining tasks before the complete demonstration

1. Restore GitHub access, fetch, and review this preserved working tree with the team's chosen frontend/integration branch. Resolve overlapping changes without discarding earlier work. Do not merge or push without the requested authorization.
2. Start the approved Django/PostgreSQL environment with migrations, institutional test records, session/CSRF configuration, OTP email delivery, and explicit administrator capabilities. Port 8000 was unavailable here.
3. Confirm the deployed API and proof contracts against `docs/product-integration.md` and `docs/blockchain-compatibility.md`. Reconcile newer lifecycle/proof semantics through reviewed adapters, preserving fail-closed behavior.
4. Configure same-origin `/api/` routing, approved public verification sources, private PDF storage/rendering, and the required real blockchain provider/worker. Enable public verification only for a confirmed real registry.
5. Run the real administrator import/issuance → student OTP/session refresh → issued passport → PDF download → anonymous reference/PDF verification → historical version → revocation/expiry journey. Include wrong-role access, missing capabilities, session expiry, logout failures, malformed files, and network/server errors.
6. Inspect the live landing with a real issued record at every requested viewport, including action availability, proof details, long names/skills, and total desktop page height. Current browser evidence covers the demo card and synthetic pagination only.

Merge blockers are unavailable real services, unconfirmed proof-contract compatibility, outstanding live visual/end-to-end acceptance, and unavailable fresh remote/conflict review.
