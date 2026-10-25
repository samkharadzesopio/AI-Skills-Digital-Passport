# Georgian PDF font support

Worktree: `C:/Users/User/sth/AI-Passport/AI-Passport-integration-merge`.
Branch: `integration`. Starting local/remote commit:
`97517dc984e210ba264e8e00a43280147f5a3ed1`.
The final commit hash is provided in the completion message (`git rev-parse HEAD`).

## Files changed

- `backend/passport_pdf_renderer.py`: embed bundled fonts for dynamic text, validate
  actual glyph coverage, measure with the same font, and hash font assets into the
  new `pymupdf-template-v4-georgian-fonts` renderer fingerprint.
- `backend/templates/NotoSansGeorgian-Regular.ttf`
- `backend/templates/NotoSansGeorgian-Bold.ttf`
- `backend/templates/NotoSansGeorgian-OFL.txt`: accompanying copyright/license.
- `backend/apps/passports/test_pdf_fonts.py`: five real rendering/embedding/overflow,
  deterministic-byte, font-fingerprint and multi-page geometry tests.
- `backend/apps/api/test_pdf.py`: registered Georgian PDF/hash/history/verification
  regression; unsupported-glyph fixture now uses an emoji rather than Georgian;
  content checks tolerate valid line wrapping while retaining geometry assertions.
- `ops/PASSPORT_PDF_APIS.md`: replace the obsolete Georgian restriction with the
  supported font/overflow behavior.
- `ops/GEORGIAN_PDF_REPORT.md`: this report and font provenance.

No template artwork, stamp assets, field positions/font sizes, models/migrations,
authentication/authorization, credential services, Passport lifecycle, document
services, public verification contracts, dependencies, or frontend code changed.
No branches, worktrees or project folders were created.

## Font and license provenance

Unmodified **Noto Sans Georgian Regular and Bold**, using the upstream **full**
static TrueType build. The full build contains Latin/numeric, Mkhedruli and Mtavruli
(uppercase Georgian) glyphs; the script-only build does not contain Latin and was
not retained. No system fonts or runtime font downloads are used.

Pinned font build: `notofonts/georgian` gh-pages commit
`4181917bda278445301ad406181f24ce36c69793`:

- [Regular source](https://github.com/notofonts/georgian/blob/4181917bda278445301ad406181f24ce36c69793/fonts/NotoSansGeorgian/full/ttf/NotoSansGeorgian-Regular.ttf)
  SHA-256: `7f7efdf31d51dd491e68c75ab57321e7611306d11137207dd43324faafcde263`.
- [Bold source](https://github.com/notofonts/georgian/blob/4181917bda278445301ad406181f24ce36c69793/fonts/NotoSansGeorgian/full/ttf/NotoSansGeorgian-Bold.ttf)
  SHA-256: `4754fba1417bc89c083961c5d2e0028c2af02dab6490b11f41a0cdee1e9bd6b3`.

Copyright 2022 The Noto Project Authors. The **SIL Open Font License 1.1** permits
bundling/embedding with software under its conditions. The exact copyright and
license text is included beside the font binaries, from
[upstream OFL.txt](https://github.com/notofonts/georgian/blob/ac0c3432fd0a6b36d052d4c29af60d197dfc00a3/OFL.txt).
No fonts were modified, renamed internally, or sold separately.

## Rendering and integrity

Dynamic names, program text, skills, descriptions, categories/subcategories and
issuer names use embedded Unicode fonts. English/numbers and the printed verification
reference remain intact. Actual font widths and PyMuPDF textbox fit results preserve
the existing boundaries; missing glyphs and genuine overflow still raise the safe
PDF rendering error (HTTP 422). No truncation, system fallback, or replacement of
Georgian characters is performed. Static template text/artwork is unchanged.

The renderer fingerprint includes both font binaries as well as existing template
and stamp assets. Changes affect explicit future generation requests through the
existing document service. No issued file, stored hash, immutable snapshot or public
reference is rewritten, and nothing is regenerated automatically. Historical and
new PDF upload verification retains authenticity/current-validity separation.

## Tests actually run

Existing repository Python 3.13 environment and disposable PostgreSQL on loopback
`127.0.0.1:55439`; settings never load production `.env`/DATABASE_URL. Environment:
`FOUNDATION_TEST_PG_HOST=127.0.0.1`, `FOUNDATION_TEST_PG_PORT=55439`,
`FOUNDATION_TEST_PG_PASSWORD=local-test-only`, `AUTH_TEST_PG_PORT=55439`.

```powershell
$python = '../AI-Skills-Digital-Passport/.venv/Scripts/python.exe'
& $python backend/manage.py test apps.passports.test_pdf_fonts apps.api.test_pdf.PassportPDFAPITests.test_georgian_pdf_is_registered_and_historical_bytes_remain_verifiable --settings=apps.integrations.postgres_test_settings --noinput --verbosity=1
& $python backend/manage.py test apps.api apps.passports apps.verification apps.integrations.test_full_workflow --settings=apps.integrations.postgres_test_settings --noinput --verbosity=1
& $python backend/manage.py check --settings=apps.integrations.postgres_test_settings
& $python backend/manage.py makemigrations --check --dry-run --settings=apps.integrations.postgres_test_settings
git diff --check
```

- New targeted checks: **6 passed** (3.202 seconds).
- Final relevant suites: **124 passed** (72.104 seconds), no failures/errors/skips.
- Django checks: no issues. Migration consistency: no changes detected.
- Template/stamp and domain/authentication file comparisons against the baseline
  show no changes. Whitespace checks passed.
- Initial test iterations exposed assertion details (font names contain spaces;
  the Georgian word also appears in a separate column; English subcategory text may
  wrap between words). The assertions now identify actual embedded fonts/columns
  and normalize line breaks, while preserving content and boundary checks.
- No complete full-backend regression was run; no shared database or deployment
  operations were performed. Expected safe failure/throttle logs are intentional tests.

Real synthetic PDFs were generated and rasterized with existing PyMuPDF. Visual
inspection covered Georgian/mixed covers and supplements, the final supplement in
an 11-skill/seven-page PDF, and the Georgian bold issuer on the credential page.
Glyphs are visible, names fit, cells remain aligned, and stamps/references remain.
The seven-page sample is 910,452 bytes, below the existing 5 MiB document limit.
An English PDF generated before the change retained its original SHA-256 throughout
QA. Automated tests verify deterministic new bytes, registered hashes, unchanged
previously issued historical bytes/hashes, and public OUTDATED/VALID verification.
Existing revocation/expiration and document-generation regressions also pass.

## Remaining limitations

Text must fit the original fixed template; unusually long names/classifications or
large descriptions still return 422. Glyphs outside the bundled font's coverage
(for example unsupported emoji/scripts) also return 422. This change does not promise
arbitrary Unicode-script support or redesign the page. No throughput/load certification
or production deployment is claimed. Existing archived reports describe earlier
checkpoints; this report and the updated API contract describe current font behavior.
