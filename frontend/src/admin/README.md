# Admin frontend integration

Live Mode uses `live/` adapters and pages over the actual Django API. See [the complete milestone report](../../../ops/ADMIN_INTEGRATION.md) for endpoint/grant contracts, acceptance evidence and limitations.

The account summary exposes only six allowlisted effective capabilities. The Admin role alone grants no actions. Read pages require `view_student_records`; Student writes, issuance, revocation, Classroom and imports use their separate grants. Backend authorization remains authoritative.

Live pages never mount the demo provider or substitute demo records on errors. DTOs are validated at runtime; pagination reconstructs fixed same-origin paths. Private queries are cancellable, account-scoped and not persisted. Existing logout/session/CSRF handling remains shared with Student authentication.

`mock.ts`, `catalog.ts`, legacy pages and `services.ts` are retained only for the explicitly labelled, development-only Demo Mode. Demo catalog/mapping edits stay in memory and official actions remain disabled. They do not change approved backend policy. Builds force Demo Mode off.

Run `npm.cmd run check:admin` for both legacy demo invariants and live grant/DTO/DOM checks. Run `python ops/test_admin_e2e.py` from the repository root with the documented loopback PostgreSQL variables for actual React/Vite/Django/PostgreSQL acceptance. The latter renders React in jsdom; it does not certify a graphical browser or OS file dialog.
