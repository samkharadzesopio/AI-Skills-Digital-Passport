# Final team integration — 2026-10-29

Target: existing `origin/integration` in
`https://github.com/samkharadzesopio/AI-Skills-Digital-Passport.git`.
Latest fetched baseline: `b2e916af0221e35bddb0a5db19c0379cc45d6923`.
Isolated candidate: `integration-candidate/final-team-20261029` in
`AI-Passport-final-team-20261029`. Owner explicitly authorizes normal integration
merge/push after essential gates. Earlier no-push handoffs are historical.

## Sources and review

- Fullstack fixes: `25241095f330e259e02110d2e6311184f451622f`.
- Sopio: `review/admin-integration-2199a37` at
  `664ce389ca24a567d9c19f6ea1bc20b8aef50770`. Most changes were already present.
  Preserved grouped navigation/latest student artwork, approved-profile preview,
  exact-digest confirmation, automatic controls and legacy completion imports.
  Retained the early stale workbook-selection guard and new assertions/docs.
- Lizi: `feature/passport-blockchain-proof` at
  `858e1b77fe4e72486a3eb6c9004d83005a16b68d`; four commits newer than baseline.
  Includes distinct Passport/credential revocation wording, owned session controls
  and read-only Amoy preflight tooling. No Amoy preflight/network call was run.
- Authentication branch `feature/integration-verification` at `63d9baf` and
  `work/2026-10-26-real-authentication` at `6b5bd0b` are baseline ancestors.
  No newer published Google OAuth implementation was found. Actual student OTP
  and administrator password/cookie-session authentication were tested.
- Older alternative frontend `fa30674` is not a newer contribution; integrating
  it wholesale would replace newer integrated Live components. Its publication
  handoff predates the current proof contract. No rollback to it was made.

All 22 original worktrees, local refs, edits/untracked file hashes and two stashes
were inventoried in external `final-team-integration-20261029/before.json`.
Only authorized `integration` advances during delivery. No developer branch was
reset, cleaned, rewritten or force-pushed. Existing services remain separate.

## Combined validation

- 185 targeted PostgreSQL tests passed: accounts, automatic source policy,
  manual import views, PDF storage, immutable snapshots/earned dates, fonts and
  public verification. System and migration-drift checks passed.
- Automatic source → PDF → actual Anvil HTTP acceptance passed, including
  independent receipt/registry commitment, neutral wording/earned date and
  preserved historical snapshot/PDF/proof. Owned cleanup passed.
- All 11 HTTP/Anvil lifecycle journeys passed: issuer/signing, confirmations,
  altered document, credential/Passport revocation, replacement, RPC outage and
  recovery, least privilege, CSRF, replay and logout. Owned cleanup passed.
- 12 Solidity tests and pinned compiler/artifact comparison passed. The first
  sandboxed Foundry invocation failed to resolve its home directory; rerunning
  with the existing permitted tool environment passed without source changes.
- Frontend build/lint and focused auth, verification, admin, spreadsheet and
  integration checks passed. Existing bundle-size warning remains.
- Lizi's real Chrome suite passed: 6 journeys, 7 viewports, 82 API responses,
  including actual revoked-Passport wording with valid underlying credentials.
- Integrated Chrome journey passed: 5 groups, 53 actual page API responses;
  real admin login/source authorization → scheduled synthetic award → student
  OTP/skill/Passport/PDF/share/history → actual Anvil confirmation → original
  VALID/altered UNVERIFIABLE → unchanged old PDF → role/CSRF denial → logout.
  API-request helper traffic is additional and not counted as page responses.
  No API responses were intercepted. Student/public screenshots were inspected.
- Initial combined Chrome attempt failed because the generic PDF fixture used
  `Active` while its approved synthetic source accepted exact `ACTIVE` only.
  Corrected the fixture status, preserved the policy, restarted only the owned
  session and passed the affected journey. Failed evidence is retained.
- New stop-file guard and disposable resource tests passed (10 tests). First
  review session stopped/cleaned through its stop file; final session stays up.

No full current backend or 401-control audit is claimed. Prior unchanged evidence
is in `E2E_RESULTS.md` and `evidence/`; secondary issues remain deferred as listed
in `REMAINING_WORK.md`. No critical blocker remains in tested local flows.

## Live local review

Frontend: `http://127.0.0.1:53690/student/login` and `/admin/login`.
Django: `http://127.0.0.1:53689/api/accounts/csrf/`.
Anvil: `http://127.0.0.1:64320` (chain 31337); owned PostgreSQL: loopback 64251.
These are actual Live Mode services with synthetic records and an isolated
synthetic Google provider. Automatic sync was disabled after acceptance; admins
can re-enable the approved synthetic source. Real Google OAuth/Sheets, SMTP,
institutional provisioning/legal basis, persistent migration rollout, public
chain and hosting are untested external gates.

Runtime metadata/private login-file path and logs:
`C:/Users/User/sth/AI-Passport/final-team-integration-20261029/live-final/`.
Student email: `browser.student@btu.edu.ge`; request an OTP in the UI and read it
privately from the file named by `review-ready.json`. Admin credentials are in
that same private file; never commit or paste them. Create `review.stop` in the
runtime directory to shut down and remove only owned resources. This supported
review process remains running until stopped; it does not promise reboot recovery.

Delivery SHA, post-merge smoke, remote equality and final service/preservation
checks are recorded externally in `final-team-integration-20261029/DELIVERY.json`
and reported to the owner after the normal push.
