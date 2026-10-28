# Official passport artwork assets

Source: repository `templates/Passport_Blank.pdf`, supplied by the user as the official four-page visual reference. The PDF itself is unchanged.

- `btu-logo.svg`: original outlined BTU logo, including Georgian lettering, extracted from page 1 vector paths. No generated logo or substitute lettering.
- `passport-title.svg`: original cover title glyph outlines from page 1. Only the title's glyph definitions and uses are retained, not a PDF page.
- `passport-asterisk.svg`: original orange decorative vector mark from page 1.
- `passport-seal.svg`: original green AI seal vector paths from page 1. The component clips it to its circular outline. It is decorative artwork, not a verification result.
- `ai_skill.png`, `ai_applied.png`, `ai_advanced.png`: byte-for-byte copies of the approved existing `backend/stamps/` files. These indicate learning formats; they are not a mandatory sequence or a blockchain verification claim.

Vector assets were exported with PyMuPDF by selecting the original artwork's bounded drawing paths, preserving drawing order and fills. The cover title uses its original SVG glyph outlines. The website does not display rendered PDF screenshots or embed PDF pages for the card.

No blockchain-verification stamp is included. No full font file was extracted or distributed; dynamic fields use system font fallbacks.
