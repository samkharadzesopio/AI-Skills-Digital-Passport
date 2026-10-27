# Official passport artwork web representation

Date: 2026-10-27. Work remains on `fix/frontend-blockchain-compatibility`. Existing staged, unstaged and untracked compatibility work is preserved. No Git reset, stash, switch, merge, commit or push was performed. No backend, database, blockchain, PDF template or PDF generation code was changed.

## Reference and branding

All four pages of `templates/Passport_Blank.pdf` were rendered and visually inspected before implementation. The source is landscape A4, 841.89 by 595.276 points. Its charcoal frame, pale-gray border, white paper, thin rules, orange emphasis and bright stamp artwork form the design reference.

The BTU logo and Georgian institutional lettering are original extracted vector paths, not a generated or retyped alternative. The large cover title retains the exact original Gilroy glyph outlines as a compact vector asset. Dynamic text is HTML with Arial/Helvetica/system fallbacks: a complete approved Gilroy webfont is not supplied in the repository. This is a remaining fidelity limitation, especially for dynamic names and body text.

The existing learning stamps were copied without modification, with automated SHA-256 comparisons against the originals. They retain their meanings: focused learning, applied learning, and extended academic learning. The About view explicitly states that they are not a compulsory sequence.

Colors sampled from PDF vector fills:

- Charcoal `#2d2d2d`, white `#ffffff`, pale gray `#e2dfe5`.
- Orange `#ff6a00`, magenta `#ff007e`, green `#31f48e`, cyan `#00dbff`.
- An accessible dark-orange text variant `#a63f00` is used for small headings on white. Primary orange buttons use black text.

The original blank artwork contains a magenta blockchain-verification mark. That claim is intentionally omitted from the web representation. Magenta is retained for an explicitly labeled sample/AI-record mark. The green seal is identified as decorative original artwork, not proof of student validity or chain confirmation.

## Pages and components changed

- `components/PassportCard.tsx` and `passport-card.css`: reusable four-view responsive passport, dynamic fields, original brand assets and learning-format stamps.
- `components/passport-card-data.ts`: adapters for existing structured demo records and actual authenticated backend snapshots. Missing fields remain missing; no invented proficiency, course, date, credential, issuer or verification result.
- `data/passport-artwork-demo.ts`: fictional Alex Example sample used only on the public landing page. It has no issued reference or date and is always marked demonstration/unverified, independent of the global Demo Mode flag.
- `verification/pages.tsx`: the interactive card is the landing-page centerpiece. Existing reference and PDF verification actions and result parsing remain intact.
- `App.tsx`: root opens public verification/landing in both Live and Demo modes. Existing private routes remain protected. Imports the common artwork theme.
- `components/PassportPreview.tsx`: the new card supplements the existing inspectable semantic record. An optional link to the unchanged blank template remains; the old PDF object embed is removed.
- `live/ProductWorkspace.tsx`: actual authorized dashboard/passport records feed the visual card. Current passport pages obtain holder fields from the existing authenticated dashboard API. Retired records do not reuse a holder's current name as a purported historical identity. Existing lifecycle controls, PDF generation/download, public sharing and capability checks remain in place.
- `layouts/VerificationLayout.tsx`, `StudentLayout.tsx`, `AdminLayout.tsx`, `auth/LoginPages.tsx`: original extracted BTU logo in existing brand lockups.
- `artwork-theme.css`: restrained charcoal/orange/paper styling across public verification, login, student/admin chrome, cards, primary buttons and Demo Mode banner. Administrator functionality and layout remain practical and intact.
- `public/brand/`: official derived vectors, unchanged stamp PNG copies, and provenance notes.
- `scripts/check-passport-card.mjs`, `check-preview.mjs`, `check-product.mjs`, `package.json`: new interaction/asset/privacy checks, new landing-route expectation, and a corrected asynchronous wait for current and historical passport views.

## Interaction and responsive behavior

Four horizontally sliding views are available: Cover, About the Passport, Verified AI Skillset, AI Skill Supplement. View buttons, previous/next controls, and ArrowLeft/ArrowRight/Home/End on the focused carousel navigate without changing routes. Touch pointer swipes navigate only when primarily horizontal. Vertical reading and horizontal supplement-table scrolling do not trigger navigation.

Inactive views have both `aria-hidden` and `inert`; a polite live region announces the selected view. Every navigation control has an accessible label and a visible keyboard focus indicator. There is no autoplay. Reduced-motion preference disables track transitions.

The card uses container sizing rather than assuming full-page width. Desktop composition follows the landscape artwork; smaller containers switch the cover and About layout, abbreviate the visual navigation labels while retaining accessible names, and allow vertical reading within the paper surface. The supplement has its own horizontal scroll region. Long names/references wrap. No root-page horizontal scrolling is intentionally introduced.

## Data and security boundaries

Public sample data is static and unmistakably fictional. It is never a fallback for failed private API requests. Authenticated cards consume the existing authorized profile and passport response, with snapshot skills and backend status. The current snapshot contract does not supply all learning-experience titles or skill-earned dates; those cells say `Not supplied`, rather than borrowing dates from PDF issuance or inventing course information.

The web card is not the issued PDF. Official PDF actions continue through the existing authenticated endpoints. Source PDF copies and generation logic are unchanged. The component cannot display a `Blockchain Verified` success badge; the existing isolated proof adapter and finalized-backend dependency remain unchanged. No claim of real blockchain success or current validity is inferred from decorative artwork.

## Tests and remaining review

Production build and lint passed. All eleven frontend regression commands passed: architecture, admin, verification, demo, preview, passport, auth, product, public-transport, compatibility, and the new passport-card check. The existing bundle-size warning remains (approximately 758 kB main JavaScript).

New tests cover all four views, button navigation, keyboard boundaries, Home/End, synthetic touch swipe, vertical-scroll isolation, supplement-scroll isolation, inactive-view accessibility attributes, reduced-motion CSS, primary body/button contrast ratios, exact stamp hashes, absence of PDF embeds, authorized data mapping, private-field omission, sample labeling, and absence of invented blockchain success. Existing authentication/CSRF/session, capability, lifecycle/replacement/history, PDF, sharing, Demo Mode isolation and failure tests passed.

Responsive rules and interaction behavior were checked in source/jsdom. **Actual desktop/tablet/mobile browser rendering was not certified:** native Chrome visual-review access returned `Computer Use was not approved to use Google Chrome`; no browser security or approval boundary was bypassed. A visual viewport review is still needed at 1440, 768 and 390 pixels, including every view, long names, many skills, keyboard focus, actual touch scrolling, zoom and reduced motion. Do not treat jsdom as a graphical layout engine.

No actual Django/PostgreSQL or chain verification was tested in this redesign. The prior PostgreSQL authentication blocker remains separate. Further dependencies are the complete approved dynamic webfont, richer authorized skill-supplement data, and the finalized blockchain proof contract. The original Classroom/Chrome integration scope remains intact.
