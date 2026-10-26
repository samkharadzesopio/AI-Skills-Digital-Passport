# BTU AI Skills Digital Passport frontend

The live Student workspace uses the existing Django session and identity-scoped APIs. See [the Student milestone report](../ops/STUDENT_INTEGRATION.md) for implementation, acceptance evidence, endpoints and remaining limitations.

## Run locally

For the guarded local PostgreSQL and file-mailbox login setup, follow [Local development](../ops/LOCAL_DEVELOPMENT.md) and use `ops/start_local.ps1` from the repository root.

Use `npm.cmd` in PowerShell when execution policy blocks `npm.ps1`.

```text
npm.cmd ci
npm.cmd run dev
```

Django must run separately with an approved local configuration. Keep `VITE_ENABLE_DEMO=false` for live Student login. Vite proxies `/api/` to `http://127.0.0.1:8000`, preserving Host/Origin for cookies and CSRF. The process environment `BTU_DEV_API_TARGET` may select another trusted local backend. Production requires an HTTPS same-origin reverse proxy and SPA route fallback; the Vite proxy is not bundled into static hosting.

For the labelled preview, put `VITE_ENABLE_DEMO=true` in ignored `frontend/.env.local` and restart Vite. Open `/student/dashboard` or `/admin/dashboard`. Demo Mode is development-only, uses sample data, disables official actions and API verification, and is forced off in production builds. A demo user is never an authenticated identity.

## Routes and records

Live Student routes include dashboard, read-only profile, skills, achievements, credentials and credential details, current Passport, version history and version details. Current and historical PDF controls request real backend generation/status/download. Sessions restore after refresh. Login/logout preserve CSRF and clear private client state; failed requests show errors without falling back to sample records.

`src/student/contracts.ts` parses Django DTOs. `service.ts` accepts no student identity selector and reconstructs safe pagination routes instead of following response URLs. `adapter.ts` represents actual category/one-subcategory snapshots. Earned achievements, current credential validity, snapshot currency and issuance remain separate facts. No proficiency, current verification or blockchain claim is inferred in React.

The existing `src/contracts/passport.ts` recursive v2 model and `src/data/passport.ts` are a proposed demo presentation, not the live Django contract. The shared component module retains that demo preview and adds `IssuedPassportPreview` for real snapshots. The original BTU template and Georgian renderer are unchanged. See `docs/passport-template-integration.md` for historical preparation notes.

Admin's existing demo interface is preserved; live management remains blocked pending explicit backend capabilities and API wiring. `/verify/*` stays public and independent of session queries. Public reference/upload configuration and existing parser limitations remain separate work. Gap Analyzer and game remain honest placeholders. No recommendation, blockchain, Neon, full Admin or redesign work is included in the Student milestone.

## Checks

Run `npm.cmd run build`, `lint`, `check:architecture`, `check:auth`, `check:student`, `check:admin`, `check:verification`, `check:demo` and `check:passport`. `check:preview` additionally requires the local demo flag and tests sample route rendering. Unit/DOM fixture tests do not prove real backend acceptance.

For real React-to-Vite-to-Django HTTP acceptance, run `python ops/test_student_e2e.py` from the repository root using the documented disposable local PostgreSQL environment. It renders actual routes in jsdom, uses real HTTP sessions/CSRF and database records, validates PDF bytes and public verification, checks refresh/logout/cache cleanup and second-student ownership denials, and removes its synthetic fixtures afterward. It does not certify graphical browser layout, keyboard/mobile behavior, live SMTP or institutional access.

English/Georgian locale preferences remain; new live record labels are English. Large-bundle splitting, complete translations and visual/accessibility acceptance remain future work.
