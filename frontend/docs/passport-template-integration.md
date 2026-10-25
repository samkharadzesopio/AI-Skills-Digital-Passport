# BTU passport template integration preparation

## Evidence and template identity

Read-only inspection located `templates/Passport_Blank.pdf` and `templates/Passpor_Filled Form.pdf`, with byte-identical respective copies under `backend/templates/`. The existing Django renderer uses `backend/templates/Passport_Blank.pdf`. Both source PDFs were rendered and all four pages visually inspected; PDF.js also reported no AcroForm fields or page widgets. They are static four-page A4-landscape PDFs, approximately 841.89 x 595.276 points, not fillable forms.

The supplied filled reference illustrates five skill stamps and supplement rows but leaves cover identity/date/Passport ID fields blank. It is a design example, not an issued student record. No student data, sample filled PDF, signatures or generated QR codes are published by this change.

The exact blank PDF is copied, unchanged, to `frontend/public/templates/btu-passport-blank.pdf`. Its source/hash/page metadata is in `src/contracts/passport-template.json`. The frontend viewer opens the original artwork; it does not recreate or populate a competing passport design. Static artwork includes issuer and BLOCKCHAIN VERIFIED wording; neither artwork nor a template preview establishes authenticity or blockchain anchoring.

Page roles:

1. Cover: NAME, SURNAME, DATE, PASSPORT ID, fixed BTU/issuer artwork.
2. Passport explanation and three stamp learning formats, PASSPORT ID footer.
3. VERIFIED AI SKILLSET: ten card slots, PASSPORT ID footer.
4. AI SKILL SUPPLEMENT: five rows with STAMP TYPE, SKILL, DESCRIPTION, EARNED THROUGH, DATE EARNED; PASSPORT ID footer.

The published template version is not present. The inspected file hash identifies this copy without inventing an official version label.

## Proposed presentation model v2

`src/contracts/passport.ts` and `passport.schema.json` now propose schemaVersion 2.0. This supersedes the earlier unapproved 1.0 frontend draft; it is not a claim of an implemented Django serializer. No automatic v1 migration or flat-to-nested backend adapter is assumed.

Identifiers have separate fields: `holder.internalStudentUuid`, `holder.externalStudentId`, `identity.passportId` (public passport reference), `identity.passportVersionId` (public version reference), and `identity.versionNumber` (ordinal). An account UUID, passport row UUID, public passport reference, version row UUID and public version reference must never be substituted for one another. Internal Student UUIDs must not be printed into public template fields.

The model retains recursive categories/subcategories, individual skill descriptions, independent proficiency assessments, learning-format stamps, multiple learning experiences, credential/evidence links, issuer identity/reference, issue/revocation timestamps/statuses and verification metadata. The three stamp types describe learning format/depth; the supplied template explicitly says they are not a mandatory sequence. Do not convert them into proficiency scores or invent an ordering.

Both `/student/passport` and `/admin/passports/preview` render `PassportPreview`; `/admin/students/:id/passport` reuses it for a clearly marked demo identity. The latter is an independent illustrative payload, not a representation of official Admin-table records. Dashboard snippets reuse the same semantic renderer without the embedded PDF. No final populated PDF layout is implemented.

## Field mapping

| Supplied template field | Frontend presentation v2 | Current backend snapshot / render field | Required action |
| --- | --- | --- | --- |
| Page 1 NAME | `holder.firstName` | `PassportVersion.student_snapshot.first_name` -> `student.first_name` | Use immutable snapshot; existing cover insertion is `(255,270)`; confirm alignment against the supplied page. |
| Page 1 SURNAME | `holder.lastName` | `student_snapshot.last_name` -> `student.last_name` | Same; existing insertion `(255,310)`. |
| Page 1 DATE | `identity.issuedAt` | `PassportVersion.issued_at` -> `version.issued_date` | Backend formats issued date, never browser/current date. Existing insertion `(655,263)`. |
| PASSPORT ID, pages 1-4 | `identity.passportId` | `DigitalPassport.public_reference` -> `passport.public_reference` | Use public reference, never `DigitalPassport.id`. Verify existing footer coordinates on every page. |
| Fixed issuer artwork | `issuer.name`, `issuer.id`, `issuer.reference` | PDF artwork/author is static; no passport-level issuer snapshot | Define authoritative passport issuer metadata. Credential issuer fields are not automatically the passport issuer. |
| No Student ID slot | `holder.externalStudentId` | `student_snapshot.external_student_id` -> `student.external_student_id` | Existing generator adds STUDENT ID at `(150,335)`; placement is an extension, not an approved template field. Obtain approval. |
| No program/education slot | `holder.program`, `holder.educationLevel` | Student snapshot; renderer currently passes both, prints program | Existing PROGRAM insertion `(150,352)` needs approval; education level has no allocated field. |
| No internal UUID slot | `holder.internalStudentUuid` | `DigitalPassport.student_id` -> canonical Student UUID | Private owner/admin DTO only; do not print as student ID or verification reference. |
| No Version ID/number slot | `identity.passportVersionId`, `versionNumber` | `PassportVersion.public_reference`, `version_number` -> `version.public_reference`, `number` | Existing cover additions VERSION ID `(510,220)` and VERSION number `(655,282)` need approved placement. Never confuse with `PassportVersion.id`. |
| No verification-reference/QR slot | `verification.reference` | Render context constructs `passport-version:<version.public_reference>` | Confirm a real public resolver, issued-only semantics and approved placement. Existing VERIFY `(510,234)` is an extension. Do not generate official QR codes. |
| No category/subcategory fields | `categories[].subcategories[]...` | Skill and version-skill snapshot have only flat `category` string | Add stable taxonomy/parent identities to authoritative snapshots and recursive render context. Obtain approved group/header/overflow layout; do not concatenate paths as a substitute for hierarchy. |
| Page 3 skill-card title / page 4 SKILL | `...skills[].name` | `PassportVersionSkill.skill_name` -> `skills[].name` | Preserve skill ID/code in the model even if not printed. Cards currently cap at ten; all remaining skills need approved continuation behavior. |
| Page 4 STAMP TYPE / page 3 stamp | `...skills[].stampType` | Version-skill `stamp_type`, `badge_asset_id`; renderer maps stamps | Keep template stamp artwork; reject unknown codes instead of silently assigning FOCUSED as `_stamp_path` currently does. |
| No distinct proficiency field | `...skills[].proficiency` | No separate assessment framework/code; renderer derives `level` from stamp type | Confirm assessment data and placement. Do not treat stamp format as an assessed proficiency level. |
| Page 4 DESCRIPTION | `...skills[].description` | Version-skill `description` -> `skills[].description` | Preserve full snapshot text; define approved font/overflow and Georgian glyph handling. |
| Page 4 EARNED THROUGH | `...skills[].learningExperiences[]` with credential/evidence links | Current renderer joins credential issuer names into `earned_through` | Filled reference contains learning-experience/course names, not just issuers. Freeze actual experience titles/IDs; preserve multiple supporting sources. |
| Page 4 DATE EARNED | `learningExperiences[].earnedOn` | Current renderer selects earliest credential issue date | Use the corresponding achievement earned date; issuance date is a different fact. Preserve distinct dates for distinct experiences. |
| No credential/evidence appendix | `credentials[]`, `evidence[]`, skill reference IDs | Credential/skill snapshot relationships exist; evidence and experience details are incomplete | Freeze/serialize required facts and agree an appendix/overflow layout. Existing `_render_credential_page` draws a new design not supplied in the approved four pages. |
| No lifecycle/verification-result slots | Passport/credential status, revoked/expiry timestamps; `verification.status` | Live Credential has issuance/revocation fields; version snapshots preserve issuance facts | Define current-status envelope versus immutable issued content. Do not mutate historical snapshots or infer validity from artwork. |

## Exact backend work required later (not performed)

1. Agree the presentation serializer/version contract, nullability, authoritative issuer identity and separate public/private fields. Keep canonical identifiers distinct and validate every credential/evidence relationship server-side.
2. Persist stable competency category and recursive subcategory identities and their parent relationships; include them in `services._snapshot_payload`, immutable version snapshots and snapshot hashing. Do not reconstruct historical taxonomy from today's catalog strings.
3. Capture skill proficiency independently of stamp type. Freeze achievement earned dates, approved course/experience titles and evidence relationships needed by the supplement. Current `_render_context` loses these distinctions by joining issuers and selecting earliest issuance dates.
4. Change `document_services._render_context` to output the same versioned tree used by the frontend. It currently returns flat `skills[]` and `credentials[]`, with no subcategories, public hierarchy IDs, evidence array or template-version contract. Update renderer traversal recursively; a transient PDF pagination traversal must not replace or discard the canonical nested tree.
5. Keep `passport_pdf_renderer.TEMPLATE` pointed at the supplied blank PDF. Approve coordinates for existing extra cover metadata, category/subcategory headers, proficiency, verification reference, credentials and evidence. Do not retain the custom credential appendix as an approved design without explicit acceptance. Preserve all skills beyond the ten-card/five-row capacities using approved page continuation rules.
6. Make text overflow observable: `_insert_box` currently ignores the return from `insert_textbox`, and `_text` silently truncates. Validate available space and use approved continuation/font rules, including embedded Georgian-capable fonts; do not silently lose data.
7. Version renderer/template/projection contracts and include their fingerprints in generation idempotency/cache keys. Existing `renderer_fingerprint` hashes the template and stamp assets; extend it for the approved hierarchical mapping and font assets. Re-render only from immutable issued snapshots.
8. Define revocation semantics explicitly. `Credential` has live revoked/expiry data; `PassportVersion` only has DRAFT/ISSUED, and `PassportDocument` has PENDING/GENERATING/ISSUED/FAILED. A top-level revoked passport result cannot be inferred from these states. Preserve issued historical facts and attach authoritative current verification/lifecycle information or create a new version according to the agreed policy.
9. Expose owner/admin-authorized presentation, generation-status and download endpoints. Wire real registry-backed public version-reference/PDF verification; the currently mounted public services use simulated repositories. A source label or renderer watermark is not verification.
10. Add PDF/contract regressions for taxonomy depth, multiple credentials/experiences/dates, long and Georgian text, page overflow, revoked support, version consistency and field alignment against this exact template. No migrations, backend services or endpoints were changed in this frontend preparation.

## Remaining approval gaps

The template has no dedicated slots for nested hierarchy, proficiency framework, Version ID, external Student ID, program/education, machine-readable verification/QR, credential/evidence detail, revocation or expiry. No issuer-signature or cryptographic-signature field was found. These facts can exist in the presentation model without inventing their final printed placement. Current public verification and HTTP generation/download integration are not authoritative/available end-to-end. Final populated visual design remains blocked on these decisions.
