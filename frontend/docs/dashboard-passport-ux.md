# Dashboard and passport viewer UX fixes

Date: 2026-10-27. Branch: `fix/frontend-blockchain-compatibility`. Existing staging state, unstaged fixes and untracked files were preserved. No reset, stash, branch switch, merge or push. No backend, blockchain, database, authentication policy, PDF template or PDF-generation changes.

## Dashboard hierarchy

`src/pages.tsx` removes the demo dashboard's large purple gradient hero. The existing shared `PassportCard` now follows a smaller personalized greeting, before statistics and learning analytics. The smaller duplicate passport in the analytics grid was removed. Sidebar routes and analytics remain intact.

`src/live/ProductWorkspace.tsx` also places the same component before the live dashboard's statistics, using only the authenticated dashboard response. A null passport produces an explicit no-passport state; missing summary data is labeled unavailable. It never falls back to a demonstration passport. Existing current/history selection, revocation/replacement guards, PDF controls, sharing, API authorization and administrator workflows remain unchanged.

## Scaling and overflow

`src/components/PassportCard.tsx` and `passport-card.css` now use a 1000-unit-wide HTML canvas with height derived from the original `841.89 / 595.276` landscape aspect ratio. This is a logical design coordinate system, not an arbitrary viewport height. `ResizeObserver` measures available width and applies one proportional transform to the entire page: text, logos, stamps, rules, borders and spacing scale together. The observer disconnects on unmount; a resize-listener fallback also cleans up.

Each slide reserves its own height using the same aspect ratio. Paper and content have visible overflow rather than a scrollbar or hidden overflow. The outer horizontal viewport clips only neighboring slides during horizontal navigation. Browser geometry tests check that actual text and data remain inside their page content area and that paper, content and canvas have no overflowing scroll extents.

At narrow mobile widths, the artwork necessarily becomes smaller. An accessible `Read this page as text` disclosure outside the card provides normal-size selectable text in ordinary document flow. It does not introduce a nested scrolling document or a second passport implementation; it uses the same selected page model. Users can also use normal browser zoom. The passport itself never vertically or horizontally scrolls.

## Deterministic pagination

`src/components/passport-pagination.ts` computes content pages independently of viewport size or resize timing. The four section types remain: Cover, About, Skillset, Supplement. Skillset and Supplement can repeat across as many pages as required.

- Skills retain their supplied order. Skill tiles use a bounded six-tile page; long names or learning-experience labels continue across tiles/pages.
- Supplement fields are wrapped by conservative Unicode grapheme budgets. Rows are split into bounded continuation fragments and packed into a fixed vertical budget. Fields are never ellipsized or silently discarded.
- All supplied learning experiences and their earned dates are preserved, including multiple experiences for one skill. The structured-data adapter previously used only the first experience; it now carries the whole array.
- Source characters remain in the page model; unit tests reconstruct each original name, description, learning experience and date from its fragments. Unknown stamp types or missing fields are not invented.
- Section buttons jump to their first page; arrows navigate every physical page. Page numbers show the actual total and, where applicable, section continuation counts. Home/End and arrow keys use the actual page count. Touch swipes remain supported, with vertical gestures excluded. Reduced motion disables transitions.
- Adjacent page content is mounted for smooth navigation; distant pages retain their model and are mounted when visited. This limits DOM work without dropping records.

## Files changed

- `src/pages.tsx`: passport-first demo dashboard and duplicate removal.
- `src/live/ProductWorkspace.tsx`: passport-first live dashboard, small greeting and honest empty/unavailable states.
- `src/components/PassportCard.tsx`: scaled canvas, dynamic page navigation, continuation rendering, observer cleanup and accessible text view.
- `src/components/passport-pagination.ts`: lossless deterministic wrapping and pagination.
- `src/components/passport-card-data.ts`: preserve every supplied learning experience.
- `src/components/passport-card.css`, `src/artwork-theme.css`: proportional page layout and secondary greeting.
- `scripts/check-passport-card.mjs`: pagination reconstruction, Unicode, observer sizing/cleanup and existing navigation/security checks.
- `scripts/check-passport-layout.mjs`, `package.json`: optional isolated Chromium viewport test command.

## Actual responsive test results

The layout checks ran in a dedicated headless Chromium runtime with a temporary Vite server and fresh browser contexts. They did not access the user's Chrome profile. API requests were blocked by the harness; no application API requests occurred. Public/demo data and a test-only fixture were used, with no Django responses mocked as successful real service results.

Passed at all requested sizes: **1920×1080, 1366×768, 1024×768, 768×1024, 390×844, 375×667**.

At each size, the browser checked all four dashboard and landing sections plus every page of a variable-data fixture. The final fixture contained 25 synthetic skills, long Unicode holder names, a long skill name, multiple learning experiences, and a multi-page description; it produced **33 stable pages** at every viewport. All pages passed aspect-ratio, internal-scroll extent, text/content boundary and document-width checks. The dashboard had one passport before its statistics and no hero banner.

Actual Chromium touch gestures passed at both mobile sizes. Keyboard Home navigation and reduced-motion computed styles passed. Normal-size readable-text output passed on mobile. Desktop and mobile screenshots were generated and visually inspected; screenshots and the JSON report are under `%TEMP%\btu-passport-layout-results`.

The earlier report's native-Chrome approval limitation is superseded for this task's **isolated headless layout testing only**. No permission boundary around the user's existing browser was bypassed. Physical-device Safari/Firefox testing is not claimed.

To reproduce the optional browser check, install Playwright and its dedicated Chromium runtime into a temporary tooling directory (not project dependencies), set `BTU_BROWSER_TOOLS` to that directory if needed, then run `npm.cmd run check:passport-layout` from `frontend`. The script defaults to `%TEMP%\btu-passport-browser-tests`.

## Regression evidence and remaining limits

Production build, lint, the eleven existing frontend checks, and the new graphical viewport check passed. The production build retains its existing large JavaScript chunk warning (approximately 763 kB).

Authentication/session/CSRF, admin capabilities, current versus historical passport selection, legal-name replacement guards, revoked/pending proof states, PDF handling, public verification, network/malformed-data failures, Demo Mode isolation and original asset/PDF hashes remain covered by the existing tests.

No real Django/PostgreSQL or blockchain end-to-end test was performed here. That earlier database credential blocker remains separate. No blockchain success is inferred, and no missing backend learning metadata is fabricated. Full approved Gilroy webfonts remain an optional fidelity dependency for dynamic text; original logo/title vectors and stamp assets are retained.
