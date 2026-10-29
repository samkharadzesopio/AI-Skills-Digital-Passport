# BTU requirements matrix

Primary source: owner-supplied comprehensive audit prompt, section 4 and scenarios A–K, plus the mandatory addendum. Existing repository reports are historical context. No separate official rubric was found in tracked files. This matrix records current-task evidence only; initial states are pending verification.

| ID | Requirement | Existing implementation / contract to inspect | Current-task evidence | Status / limits |
| --- | --- | --- | --- | --- |
| R01 | One permanent passport per student | DigitalPassport uniqueness, student relationship and publication services | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS local: focused acceptance preserves one existing identity |
| R02 | Permanent Passport ID | Passport public reference and immutable identity | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS local: unchanged permanent identity/reference |
| R03 | Google Sheets as primary awarded-skill source | Bounded authorized source profiles and synthetic provider | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS synthetic provider; real Google blocked/excluded |
| R04 | Automatic discovery/processing of newly confirmed skills | Documented workers, sync commands and source policy | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS local: explicit opt-in, background discovery and disable; production scheduling not deployed |
| R05 | Student ID / Skill ID matching | Spreadsheet validation, exact external identifiers | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS targeted exact-ID and unknown-ID exclusion |
| R06 | Record ID deduplication | Award receipt constraints and replay/conflict handling | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS targeted replay/concurrency and unchanged-source guards |
| R07 | CONFIRMED / PENDING / REJECTED | Approved profile parsing and eligibility enforcement | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS targeted plus Chrome pending-to-confirmed/exclusions |
| R08 | Automatic multi-page PDF creation/update | Publication outbox, PDF renderer, stored artifact contract | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS local final flow and six multi-page Georgian fixture PDFs |
| R09 | Preserve skills and first issue date | Achievement provenance and frozen snapshots | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS local original identity/date/skills/history preserved |
| R10 | Version management / historical integrity | Version uniqueness, latest effective state, frozen PDFs | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS targeted snapshot constraints and historical artifact preservation |
| R11 | Blockchain verification of official versions | Existing integrated Anvil chain path | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS actual local Anvil; no public-chain claim |
| R12 | Document integrity | Registered bytes/hash and modified evidence verification | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS actual HTTP original VALID/altered not VALID |
| R13 | Independent BTU issuer authenticity | Trusted institutional issuer and authorized on-chain signer | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS local authorized issuer/signer and independent commitment check; institutional provisioning external |
| R14 | Version-specific verification identifier | Version/document references and public routing | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS version reference; embedded link/QR deferred PD-04 |
| R15 | Anonymous public verification | Reference/PDF endpoints and React public routes | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS priority public HTTP and prior native browser flows |
| R16 | Secure student access | Existing OTP prerequisite, ownership, downloads and permissions | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS existing OTP/Admin prerequisite and PDF ownership tests; Google Sign-In excluded |
| R17 | Architecture for at least 5,000 passports/year | Existing scale tests, query budgets, bounded imports and workers | Current-task evidence: E2E_RESULTS.md and evidence/ | NOT REASSESSED: no current capacity claim |
| R18 | No issuance from invalid/unapproved/wrong-student evidence | Input validation, source authorization and transactions | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS targeted invalid/status/permission/source-policy guards |
| R19 | Administrator capability enforcement and CSRF | Existing grants and per-operation contracts | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS targeted existing grant/CSRF checks; no role-policy change |
| R20 | Separate Demo and Live behavior | Development-only demo and live API adapters | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS existing mode guards and focused Demo dialog; secondary coverage deferred |
| R21 | Preserve parallel developer work | Setup snapshots and task worktree ownership | Current-task evidence: E2E_RESULTS.md and evidence/ | PASS preservation checks on original16 worktrees/refs/stashes/edit |
| R22 | Every existing control tested with evidence | Functional inventory plus native browser/API/database checks | Current-task evidence: E2E_RESULTS.md and evidence/ | PARTIAL by owner directive:401 inventoried,203 exercised in initial wave,198 deferred; exercised is not pass count |

The three-register specification, existing 20-column workbook, approved profile schema and legacy course-completion format are separate contracts. Tests generate fictional workbooks; the tracked student workbook is not opened or imported.
