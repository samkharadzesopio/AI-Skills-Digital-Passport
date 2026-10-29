# Functional inventory

Source inventory at baseline b2e916af0221e35bddb0a5db19c0379cc45d6923. 48 route patterns and 401 distinct existing actions. Every record is pending runtime evidence unless explicitly updated after execution. Detailed required fields, intent/source, grants, expected mutations/errors and later test/retest results are in FUNCTIONAL_INVENTORY.json. Source existence is not PASS. New approved automation controls will be appended with new IDs.

## Route inventory

```json
[
    {
        "route":  "/student/login",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "student",
        "test_status":  "PENDING",
        "notes":  "Existing role boundary except login"
    },
    {
        "route":  "/student",
        "type":  "redirect",
        "redirect_to":  "/student/dashboard",
        "source_file":  "frontend/src/App.tsx",
        "scope":  "student",
        "test_status":  "PENDING",
        "notes":  "Preserve search and hash."
    },
    {
        "route":  "/student/dashboard",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "student",
        "test_status":  "PENDING",
        "notes":  "Existing role boundary except login"
    },
    {
        "route":  "/student/skills",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "student",
        "test_status":  "PENDING",
        "notes":  "Existing role boundary except login"
    },
    {
        "route":  "/student/achievements",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "student",
        "test_status":  "PENDING",
        "notes":  "Existing role boundary except login"
    },
    {
        "route":  "/student/credentials",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "student",
        "test_status":  "PENDING",
        "notes":  "Existing role boundary except login"
    },
    {
        "route":  "/student/credentials/:id",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "student",
        "test_status":  "PENDING",
        "notes":  "Existing role boundary except login"
    },
    {
        "route":  "/student/passport",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "student",
        "test_status":  "PENDING",
        "notes":  "Demo Mode redirects to /student/dashboard; Live Mode renders issued snapshot."
    },
    {
        "route":  "/student/passport/versions",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "student",
        "test_status":  "PENDING",
        "notes":  "Existing role boundary except login"
    },
    {
        "route":  "/student/passport/versions/:id",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "student",
        "test_status":  "PENDING",
        "notes":  "Existing role boundary except login"
    },
    {
        "route":  "/student/history",
        "type":  "redirect",
        "redirect_to":  "/student/passport/versions",
        "source_file":  "frontend/src/App.tsx",
        "scope":  "student",
        "test_status":  "PENDING",
        "notes":  "Preserve search and hash."
    },
    {
        "route":  "/student/profile",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "student",
        "test_status":  "PENDING",
        "notes":  "Existing role boundary except login"
    },
    {
        "route":  "/student/gap-analyzer",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "student",
        "test_status":  "PENDING",
        "notes":  "Existing role boundary except login"
    },
    {
        "route":  "/student/game",
        "type":  "redirect",
        "redirect_to":  "/student/dashboard",
        "source_file":  "frontend/src/App.tsx",
        "scope":  "student",
        "test_status":  "PENDING",
        "notes":  "Preserve search and hash."
    },
    {
        "route":  "/student/*",
        "type":  "fallback",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "student",
        "test_status":  "PENDING",
        "notes":  "Existing role boundary except login"
    },
    {
        "route":  "/admin/login",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "Existing role boundary except login"
    },
    {
        "route":  "/admin",
        "type":  "redirect",
        "redirect_to":  "/admin/dashboard",
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "Preserve search and hash."
    },
    {
        "route":  "/admin/dashboard",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "AccessBoundary + capability Gate (Live)"
    },
    {
        "route":  "/admin/students",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "AccessBoundary + capability Gate (Live)"
    },
    {
        "route":  "/admin/students/:id",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "AccessBoundary + capability Gate (Live)"
    },
    {
        "route":  "/admin/students/:id/passport",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "AccessBoundary + capability Gate (Live)"
    },
    {
        "route":  "/admin/passports/preview",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "AccessBoundary + capability Gate (Live)"
    },
    {
        "route":  "/admin/skills",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "AccessBoundary + capability Gate (Live)"
    },
    {
        "route":  "/admin/course-mappings",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "AccessBoundary + capability Gate (Live)"
    },
    {
        "route":  "/admin/courses",
        "type":  "redirect",
        "redirect_to":  "/admin/course-mappings",
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "Preserve search and hash."
    },
    {
        "route":  "/admin/credentials",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "AccessBoundary + capability Gate (Live)"
    },
    {
        "route":  "/admin/credentials/:id",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "AccessBoundary + capability Gate (Live)"
    },
    {
        "route":  "/admin/classroom-sync",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "AccessBoundary + capability Gate (Live)"
    },
    {
        "route":  "/admin/sync",
        "type":  "redirect",
        "redirect_to":  "/admin/classroom-sync",
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "Preserve search and hash."
    },
    {
        "route":  "/admin/imports",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "AccessBoundary + capability Gate (Live)"
    },
    {
        "route":  "/admin/audit-logs",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "AccessBoundary + capability Gate (Live)"
    },
    {
        "route":  "/admin/audit",
        "type":  "redirect",
        "redirect_to":  "/admin/audit-logs",
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "Preserve search and hash."
    },
    {
        "route":  "/admin/*",
        "type":  "fallback",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "admin",
        "test_status":  "PENDING",
        "notes":  "AccessBoundary + capability Gate (Live)"
    },
    {
        "route":  "/verify",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "verify",
        "test_status":  "PENDING",
        "notes":  "Public anonymous; no session hooks"
    },
    {
        "route":  "/verify/reference",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "verify",
        "test_status":  "PENDING",
        "notes":  "Public anonymous; no session hooks"
    },
    {
        "route":  "/verify/upload",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "verify",
        "test_status":  "PENDING",
        "notes":  "Public anonymous; no session hooks"
    },
    {
        "route":  "/verify/result",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "verify",
        "test_status":  "PENDING",
        "notes":  "Public anonymous; no session hooks"
    },
    {
        "route":  "/verify/qr",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "verify",
        "test_status":  "PENDING",
        "notes":  "Public anonymous; no session hooks"
    },
    {
        "route":  "/verify/qr/:reference",
        "type":  "view",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "verify",
        "test_status":  "PENDING",
        "notes":  "Public anonymous; no session hooks"
    },
    {
        "route":  "/verify/*",
        "type":  "fallback",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "verify",
        "test_status":  "PENDING",
        "notes":  "Public anonymous; no session hooks"
    },
    {
        "route":  "/",
        "type":  "redirect",
        "redirect_to":  "/verify",
        "source_file":  "frontend/src/App.tsx",
        "scope":  "global",
        "test_status":  "PENDING",
        "notes":  "Preserve search/hash"
    },
    {
        "route":  "/skills",
        "type":  "redirect",
        "redirect_to":  "/student/skills",
        "source_file":  "frontend/src/App.tsx",
        "scope":  "global",
        "test_status":  "PENDING",
        "notes":  "Preserve search/hash; target game then redirects dashboard"
    },
    {
        "route":  "/credentials",
        "type":  "redirect",
        "redirect_to":  "/student/credentials",
        "source_file":  "frontend/src/App.tsx",
        "scope":  "global",
        "test_status":  "PENDING",
        "notes":  "Preserve search/hash; target game then redirects dashboard"
    },
    {
        "route":  "/passport",
        "type":  "redirect",
        "redirect_to":  "/student/passport",
        "source_file":  "frontend/src/App.tsx",
        "scope":  "global",
        "test_status":  "PENDING",
        "notes":  "Preserve search/hash; target game then redirects dashboard"
    },
    {
        "route":  "/profile",
        "type":  "redirect",
        "redirect_to":  "/student/profile",
        "source_file":  "frontend/src/App.tsx",
        "scope":  "global",
        "test_status":  "PENDING",
        "notes":  "Preserve search/hash; target game then redirects dashboard"
    },
    {
        "route":  "/gap-analyzer",
        "type":  "redirect",
        "redirect_to":  "/student/gap-analyzer",
        "source_file":  "frontend/src/App.tsx",
        "scope":  "global",
        "test_status":  "PENDING",
        "notes":  "Preserve search/hash; target game then redirects dashboard"
    },
    {
        "route":  "/game",
        "type":  "redirect",
        "redirect_to":  "/student/game",
        "source_file":  "frontend/src/App.tsx",
        "scope":  "global",
        "test_status":  "PENDING",
        "notes":  "Preserve search/hash; target game then redirects dashboard"
    },
    {
        "route":  "/*",
        "type":  "fallback",
        "redirect_to":  null,
        "source_file":  "frontend/src/App.tsx",
        "scope":  "global",
        "test_status":  "PENDING",
        "notes":  "Page not found with /verify link"
    }
]
```

## Distinct actions

| ID | Route/context | Mode | Action | Intended function | Status |
| --- | --- | --- | --- | --- | --- |
| F-001 | All routes (Demo) | Demo | Demo banner: Student | Navigate to /student/dashboard; maintain explicit sample-data / official-actions-disabled banner. | PENDING |
| F-002 | All routes (Demo) | Demo | Demo banner: Admin | Navigate to /admin/dashboard; maintain explicit sample-data / official-actions-disabled banner. | PENDING |
| F-003 | All routes (Demo) | Demo | Demo banner: Verification | Navigate to /verify; maintain explicit sample-data / official-actions-disabled banner. | PENDING |
| F-004 | /student/* | Live and Demo | Skip to content | Move keyboard focus to main content anchor. | PENDING |
| F-005 | /student/* | Live and Demo | Brand: My Passport | Navigate to /student/dashboard. | PENDING |
| F-006 | /student/* | Live and Demo | Toggle mobile navigation | Open/close mobile sidebar and retain usable navigation on narrow screens. | PENDING |
| F-007 | /student/* | Live and Demo | Close navigation scrim | Dismiss open mobile sidebar. | PENDING |
| F-008 | /student/* | Live and Demo | Student navigation: My Passport | Navigate to /student/dashboard and close mobile sidebar; Coming Soon label on Gap Analyzer. | PENDING |
| F-009 | /student/* | Live and Demo | Student navigation: My Skills | Navigate to /student/skills and close mobile sidebar; Coming Soon label on Gap Analyzer. | PENDING |
| F-010 | /student/* | Live and Demo | Student navigation: Passport History | Navigate to /student/passport/versions and close mobile sidebar; Coming Soon label on Gap Analyzer. | PENDING |
| F-011 | /student/* | Live and Demo | Student navigation: Skills Gap Analyzer | Navigate to /student/gap-analyzer and close mobile sidebar; Coming Soon label on Gap Analyzer. | PENDING |
| F-012 | /student/* | Live and Demo | Student navigation: Public Verification | Navigate to /verify and close mobile sidebar; Coming Soon label on Gap Analyzer. | PENDING |
| F-013 | /student/* | Demo | Log Out - Demo disabled | Remain unavailable; Demo Mode has no real authenticated session. | PENDING |
| F-014 | /student/* | Live | Refresh records | Revalidate existing session and student queries; disable while refreshing. Read-only inventory: authentication files reserved to Lizi. | PENDING |
| F-015 | /admin/* | Demo | Skip to Admin content | Move to #admin-main content. | PENDING |
| F-016 | /admin/* | Demo | Admin brand | Navigate to /admin/dashboard. | PENDING |
| F-017 | /admin/* | Demo | Open navigation | Toggle mobile Admin sidebar. | PENDING |
| F-018 | /admin/* | Demo | Close navigation scrim | Dismiss open mobile sidebar. | PENDING |
| F-019 | /admin/* | Demo | EN / KA | Toggle persisted UI locale/document language; translated existing labels update. Live record labels currently documented English-only. | PENDING |
| F-020 | /admin/* | Live | Skip to Admin content | Move to #admin-main content. | PENDING |
| F-021 | /admin/* | Live | Admin brand | Navigate to /admin/dashboard. | PENDING |
| F-022 | /admin/* | Live | Open navigation | Toggle mobile Admin sidebar. | PENDING |
| F-023 | /admin/* | Live | Close navigation scrim | Dismiss open mobile sidebar. | PENDING |
| F-024 | /admin/* | Live | EN / KA | Toggle persisted UI locale/document language; translated existing labels update. Live record labels currently documented English-only. | PENDING |
| F-025 | /admin/* | Demo | Escape closes Demo mobile navigation | Dismiss open Demo Admin navigation via Escape key. | PENDING |
| F-026 | /admin/* | Demo | Reset demo changes | Replace task-local in-memory Admin fixture data with initial synthetic fixture; no backend requests. | PENDING |
| F-027 | /admin/* | Live and Demo | Admin navigation: Dashboard | Navigate to /admin/dashboard; close mobile menu; Live item visible only for its grant. | PENDING |
| F-028 | /admin/* | Live and Demo | Admin navigation: Students | Navigate to /admin/students; close mobile menu; Live item visible only for its grant. | PENDING |
| F-029 | /admin/* | Live and Demo | Admin navigation: Skills Catalog | Navigate to /admin/skills; close mobile menu; Live item visible only for its grant. | PENDING |
| F-030 | /admin/* | Live and Demo | Admin navigation: Activity-to-Skill Mapping | Navigate to /admin/course-mappings; close mobile menu; Live item visible only for its grant. | PENDING |
| F-031 | /admin/* | Live and Demo | Admin navigation: Data Imports | Navigate to /admin/imports; close mobile menu; Live item visible only for its grant. | PENDING |
| F-032 | /admin/* | Live and Demo | Admin navigation: Credentials | Navigate to /admin/credentials; close mobile menu; Live item visible only for its grant. | PENDING |
| F-033 | /admin/* | Live and Demo | Admin navigation: Verification | Navigate to /verify; close mobile menu; Live item visible only for its grant. | PENDING |
| F-034 | /admin/* | Live and Demo | Admin navigation: Passport Records | Navigate to /admin/passports/preview; close mobile menu; Live item visible only for its grant. | PENDING |
| F-035 | /admin/* | Live and Demo | Admin navigation: Audit Logs | Navigate to /admin/audit-logs; close mobile menu; Live item visible only for its grant. | PENDING |
| F-036 | /admin/* | Live and Demo | Admin navigation: BTU Classroom Sync - Simulated | Navigate to /admin/classroom-sync; close mobile menu; Live item visible only for its grant. | PENDING |
| F-037 | /verify/* | Live and Demo | Skip to verification | Move to #verification-main. | PENDING |
| F-038 | /verify/* | Live and Demo | Verification brand | Navigate to /verify. | PENDING |
| F-039 | /verify/* | Live and Demo | English / Georgian | Toggle existing translated public interface and persisted locale. | PENDING |
| F-040 | /*, /student/*, /admin/* | Live and Demo | Unknown-page public verification link | Display page-not-found with link to /verify; no fabricated object. | PENDING |
| F-041 | /student/login | Live and Demo | Brand/public verification | Navigate to /verify without login. Read-only inventory; any fix handed to Lizi. | PENDING |
| F-042 | /student/login | Live and Demo | English / Georgian | Toggle translated auth labels and persisted locale. Read-only inventory; any fix handed to Lizi. | PENDING |
| F-043 | /student/login | Live and Demo | Student tab | Navigate to /student/login. Read-only inventory; any fix handed to Lizi. | PENDING |
| F-044 | /student/login | Live and Demo | Administrator tab | Navigate to /admin/login. Read-only inventory; any fix handed to Lizi. | PENDING |
| F-045 | /student/login | Live and Demo | Public Verification | Navigate to /verify without authentication. Read-only inventory; any fix handed to Lizi. | PENDING |
| F-046 | /student/login | Demo | Open Demo workspace | Navigate to /student/dashboard; no credentials requested. | PENDING |
| F-047 | /student/login | Live | University email | Enter bounded valid university email; reject disallowed format/domain; read-only auth inventory. | PENDING |
| F-048 | /student/login | Live | Retry session restoration | Refetch failed existing session request; respect cooldown; no auth redesign. | PENDING |
| F-049 | /student/login | Live | Request OTP | Request generic OTP response without account enumeration; synthetic local mail only. Authentication ownership remains Lizi. | PENDING |
| F-050 | /student/login | Live | Six-digit OTP | Enter six numeric OTP digits; never log secrets. Authentication ownership remains Lizi. | PENDING |
| F-051 | /student/login | Live | Verify OTP | Verify code, restore session, navigate to Student dashboard on authoritative success. Authentication ownership remains Lizi. | PENDING |
| F-052 | /student/login | Live | Resend code | Request new OTP after existing 60-second resend cooldown. Authentication ownership remains Lizi. | PENDING |
| F-053 | /student/login | Live | Change email | Return to email step; clear OTP/notice/error. Authentication ownership remains Lizi. | PENDING |
| F-054 | /admin/login | Live and Demo | Brand/public verification | Navigate to /verify without login. Read-only inventory; any fix handed to Lizi. | PENDING |
| F-055 | /admin/login | Live and Demo | English / Georgian | Toggle translated auth labels and persisted locale. Read-only inventory; any fix handed to Lizi. | PENDING |
| F-056 | /admin/login | Live and Demo | Student tab | Navigate to /student/login. Read-only inventory; any fix handed to Lizi. | PENDING |
| F-057 | /admin/login | Live and Demo | Administrator tab | Navigate to /admin/login. Read-only inventory; any fix handed to Lizi. | PENDING |
| F-058 | /admin/login | Live and Demo | Public Verification | Navigate to /verify without authentication. Read-only inventory; any fix handed to Lizi. | PENDING |
| F-059 | /admin/login | Demo | Open Demo workspace | Navigate to /admin/dashboard; no credentials requested. | PENDING |
| F-060 | /admin/login | Live | University email | Enter bounded valid university email; reject disallowed format/domain; read-only auth inventory. | PENDING |
| F-061 | /admin/login | Live | Retry session restoration | Refetch failed existing session request; respect cooldown; no auth redesign. | PENDING |
| F-062 | /admin/login | Live | Administrator password | Enter existing bounded password securely; clear after submission. | PENDING |
| F-063 | /admin/login | Live | Sign in administrator | Use existing password session/CSRF flow and navigate after restored role match. | PENDING |
| F-064 | /student/* | Live | Log out | Cancel private requests, clear private caches after authoritative logout and return to role login; failure stays visible. Read-only authentication inventory. | PENDING |
| F-065 | /student/* | Live | Retry protected session | Retry unavailable session after cooldown; do not mount private workspace on unverified access. | PENDING |
| F-066 | /student/* | Live | Blocked-access Public Verification | Navigate to anonymous /verify while blocked/wrong-role. | PENDING |
| F-067 | /admin/* | Live | Log out | Cancel private requests, clear private caches after authoritative logout and return to role login; failure stays visible. Read-only authentication inventory. | PENDING |
| F-068 | /admin/* | Live | Retry protected session | Retry unavailable session after cooldown; do not mount private workspace on unverified access. | PENDING |
| F-069 | /admin/* | Live | Blocked-access Public Verification | Navigate to anonymous /verify while blocked/wrong-role. | PENDING |
| F-070 | /student/* | Demo | Retry demo Student data | Retry synthetic Student loader without API or official records. | PENDING |
| F-071 | /admin/* | Demo | Retry demo Admin data | Retry synthetic Admin loader; no official records substituted into Live Mode. | PENDING |
| F-072 | /student/dashboard | Live | Retry records | Retry read-only current Student endpoint after failure; foreign/malformed records stay unavailable. | PENDING |
| F-073 | /student/profile | Live | Retry records | Retry read-only current Student endpoint after failure; foreign/malformed records stay unavailable. | PENDING |
| F-074 | /student/skills | Live | Retry records | Retry read-only current Student endpoint after failure; foreign/malformed records stay unavailable. | PENDING |
| F-075 | /student/achievements | Live | Retry records | Retry read-only current Student endpoint after failure; foreign/malformed records stay unavailable. | PENDING |
| F-076 | /student/credentials | Live | Retry records | Retry read-only current Student endpoint after failure; foreign/malformed records stay unavailable. | PENDING |
| F-077 | /student/credentials/:id | Live | Retry records | Retry read-only current Student endpoint after failure; foreign/malformed records stay unavailable. | PENDING |
| F-078 | /student/passport | Live | Retry records | Retry read-only current Student endpoint after failure; foreign/malformed records stay unavailable. | PENDING |
| F-079 | /student/passport/versions | Live | Retry records | Retry read-only current Student endpoint after failure; foreign/malformed records stay unavailable. | PENDING |
| F-080 | /student/passport/versions/:id | Live | Retry records | Retry read-only current Student endpoint after failure; foreign/malformed records stay unavailable. | PENDING |
| F-081 | /student/skills | Live | Previous records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-082 | /student/skills | Live | Next records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-083 | /student/achievements | Live | Previous records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-084 | /student/achievements | Live | Next records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-085 | /student/credentials | Live | Previous records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-086 | /student/credentials | Live | Next records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-087 | /student/passport/versions | Live | Previous records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-088 | /student/passport/versions | Live | Next records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-089 | /student/skills | Live | Full paginated achievement list | Navigate to /student/achievements; preserve ownership and appropriate read-only state. | PENDING |
| F-090 | /student/credentials | Live | Credential public-reference detail | Navigate to /student/credentials/:id; preserve ownership and appropriate read-only state. | PENDING |
| F-091 | /student/credentials/:id | Live | Back to credentials | Navigate to /student/credentials; preserve ownership and appropriate read-only state. | PENDING |
| F-092 | /student/credentials/:id | Live | Credential self detail | Navigate to /student/credentials/:id; preserve ownership and appropriate read-only state. | PENDING |
| F-093 | /student/passport | Live | View Passport version history | Navigate to /student/passport/versions; preserve ownership and appropriate read-only state. | PENDING |
| F-094 | /student/passport/versions | Live | Current Passport | Navigate to /student/passport; preserve ownership and appropriate read-only state. | PENDING |
| F-095 | /student/passport/versions | Live | Version detail link | Navigate to /student/passport/versions/:id; preserve ownership and appropriate read-only state. | PENDING |
| F-096 | /student/passport/versions/:id | Live | Back to version history | Navigate to /student/passport/versions; preserve ownership and appropriate read-only state. | PENDING |
| F-097 | /student/credentials/:id | Live | Public verification | Open /verify/reference?kind=credential&reference=<public reference>; no internal ID/private profile exposed. | PENDING |
| F-098 | /student/dashboard | Live | Share Passport | Copy anonymous public Passport verification URL and show read-only URL; only current confirmed proof can enable sharing. | PENDING |
| F-099 | /student/dashboard | Live | Public verification link field | Expose selectable read-only public URL; no private PDF/download URL is shared. | PENDING |
| F-100 | /student/dashboard | Live | Verify Passport | Navigate to public Passport reference form. | PENDING |
| F-101 | /student/dashboard | Live | View History | Navigate to /student/passport/versions; available for no-issued empty state too. | PENDING |
| F-102 | /student/dashboard | Live | Read-only Student identity and record details | Expand/collapse actual maintained identity; no edit controls. | PENDING |
| F-103 | /student/dashboard | Live | View university-maintained identity | Navigate to /student/profile. | PENDING |
| F-104 | /student/dashboard | Demo | Download PDF - Demo disabled | Remain disabled; no issued document/reference/history is represented by synthetic samples. | PENDING |
| F-105 | /student/dashboard | Demo | Share Passport - Demo disabled | Remain disabled; no issued document/reference/history is represented by synthetic samples. | PENDING |
| F-106 | /student/dashboard | Demo | View History - Demo disabled | Remain disabled; no issued document/reference/history is represented by synthetic samples. | PENDING |
| F-107 | /student/dashboard | Live and Demo | Previous passport view | Move exactly one page backward; disabled on first page. | PENDING |
| F-108 | /student/dashboard | Live and Demo | Next passport view | Move exactly one page forward including overflow pages; disabled on last page. | PENDING |
| F-109 | /student/dashboard | Live and Demo | Cover section | Navigate to first cover page; aria-pressed updates. | PENDING |
| F-110 | /student/dashboard | Live and Demo | About section | Navigate to first About page; aria-pressed updates. | PENDING |
| F-111 | /student/dashboard | Live and Demo | Verified AI Skillset section | Navigate to first skillset page; preserve all overflow records. | PENDING |
| F-112 | /student/dashboard | Live and Demo | AI Skill Supplement section | Navigate to first supplement page; preserve all overflow rows. | PENDING |
| F-113 | /student/dashboard | Live and Demo | ArrowLeft | Go one page backward from carousel focus; do not hijack form/button/text view keys. | PENDING |
| F-114 | /student/dashboard | Live and Demo | ArrowRight | Go one page forward from carousel focus. | PENDING |
| F-115 | /student/dashboard | Live and Demo | Home | Go to first Passport page. | PENDING |
| F-116 | /student/dashboard | Live and Demo | End | Go to final Passport page. | PENDING |
| F-117 | /student/dashboard | Live and Demo | Touch swipe left | Advance a page for horizontal swipe exceeding threshold; ignore vertical scroll. | PENDING |
| F-118 | /student/dashboard | Live and Demo | Touch swipe right | Return a page for horizontal swipe exceeding threshold; clamp boundaries. | PENDING |
| F-119 | /student/dashboard | Live and Demo | Read this page as text | Expand/collapse semantic current page content; expose same actual records. | PENDING |
| F-120 | /student/dashboard, /student/passport | Live | Retry PDF status | Refetch selected exact-version registered PDF metadata; safe failure state. | PENDING |
| F-121 | /student/dashboard, /student/passport | Live | Generate Passport PDF | Generate or reuse exact issued snapshot PDF; block while busy/preparing/cooldown. | PENDING |
| F-122 | /student/dashboard, /student/passport | Live | Retry PDF generation | Retry existing failed exact-version generation; retain safe error handling. | PENDING |
| F-123 | /student/dashboard, /student/passport | Live | Download registered PDF | Fetch real exact-version PDF and safe fixed filename; start browser download; revoke Blob URL. | PENDING |
| F-124 | /student/passport/versions/:id | Live | Retry PDF status | Refetch selected exact-version registered PDF metadata; safe failure state. | PENDING |
| F-125 | /student/passport/versions/:id | Live | Generate Passport PDF | Generate or reuse exact issued snapshot PDF; block while busy/preparing/cooldown. | PENDING |
| F-126 | /student/passport/versions/:id | Live | Retry PDF generation | Retry existing failed exact-version generation; retain safe error handling. | PENDING |
| F-127 | /student/passport/versions/:id | Live | Download registered PDF | Fetch real exact-version PDF and safe fixed filename; start browser download; revoke Blob URL. | PENDING |
| F-128 | /student/passport, /student/passport/versions/:id, /admin/students/:id/passport, /admin/passports/preview | Live | Verify current Passport | Open anonymous Passport public-reference verification; never treat preview as proof. | PENDING |
| F-129 | /student/passport, /student/passport/versions/:id, /admin/students/:id/passport, /admin/passports/preview | Live | Public verification link for this version | Open version-specific public QR-compatible review form with immutable public version reference. | PENDING |
| F-130 | /student/passport, /student/passport/versions/:id, /admin/students/:id/passport, /admin/passports/preview | Live | Category disclosure | Expand/collapse actual frozen category skills. | PENDING |
| F-131 | /student/passport, /student/passport/versions/:id, /admin/students/:id/passport, /admin/passports/preview | Live | Subcategory disclosure | Expand/collapse frozen subcategory skills; no invented proficiency/hierarchy. | PENDING |
| F-132 | /admin/passports/preview, /admin/students/:id/passport | Demo | View supplied blank BTU template | Expand unfilled supplied PDF reference; artwork never constitutes verification. | PENDING |
| F-133 | /admin/passports/preview, /admin/students/:id/passport | Demo | Open unfilled template PDF | Open bundled blank reference PDF in separate tab with noopener. | PENDING |
| F-134 | /admin/passports/preview, /admin/students/:id/passport | Demo | Inspect passport data and hierarchy | Expand/collapse synthetic structured Passport details. | PENDING |
| F-135 | /admin/passports/preview, /admin/students/:id/passport | Demo | Subcategory disclosure | Expand/collapse recursive synthetic subcategory. | PENDING |
| F-136 | /admin/dashboard | Live | Retry records | Retry failed authorized read after Retry-After; show no demo substitution. | PENDING |
| F-137 | /admin/students | Live | Retry records | Retry failed authorized read after Retry-After; show no demo substitution. | PENDING |
| F-138 | /admin/students/:id | Live | Retry records | Retry failed authorized read after Retry-After; show no demo substitution. | PENDING |
| F-139 | /admin/credentials | Live | Retry records | Retry failed authorized read after Retry-After; show no demo substitution. | PENDING |
| F-140 | /admin/credentials/:id | Live | Retry records | Retry failed authorized read after Retry-After; show no demo substitution. | PENDING |
| F-141 | /admin/skills | Live | Retry records | Retry failed authorized read after Retry-After; show no demo substitution. | PENDING |
| F-142 | /admin/course-mappings | Live | Retry records | Retry failed authorized read after Retry-After; show no demo substitution. | PENDING |
| F-143 | /admin/dashboard | Live | Import Activity Records | Navigate to /admin/imports; history labels describe actual import runs, not complete security audit. | PENDING |
| F-144 | /admin/dashboard | Live | Review Credentials | Navigate to /admin/credentials; history labels describe actual import runs, not complete security audit. | PENDING |
| F-145 | /admin/dashboard | Live | View Students | Navigate to /admin/students; history labels describe actual import runs, not complete security audit. | PENDING |
| F-146 | /admin/dashboard | Live | Review import errors | Navigate to /admin/imports; history labels describe actual import runs, not complete security audit. | PENDING |
| F-147 | /admin/dashboard | Live | Recent Import run | Navigate to /admin/imports; history labels describe actual import runs, not complete security audit. | PENDING |
| F-148 | /admin/dashboard | Live | Inspect import results and history | Navigate to /admin/imports; history labels describe actual import runs, not complete security audit. | PENDING |
| F-149 | /admin/dashboard | Live | Refresh dashboard | Refetch real statistics; unavailable review/global-error counts stay honestly unavailable. | PENDING |
| F-150 | /admin/dashboard | Live | Retry recent imports | Retry persisted import-run projection only with import grant. | PENDING |
| F-151 | /admin/students | Live | New Student record | Toggle canonical Student create form without creating login/invitation. | PENDING |
| F-152 | /admin/students | Live | Search name/email/student ID | Apply bounded server search and reset to page 1. | PENDING |
| F-153 | /admin/students | Live | Program filter | Apply existing exact program filter and reset page. | PENDING |
| F-154 | /admin/students | Live | Education level filter | Apply existing exact education-level filter and reset page. | PENDING |
| F-155 | /admin/students | Live | Student status filter | Apply existing exact status filter and reset page. | PENDING |
| F-156 | /admin/students | Live | Student row detail | Navigate to canonical selected Student UUID record. | PENDING |
| F-157 | /admin/students | Live | Previous records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-158 | /admin/students | Live | Next records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-159 | /admin/students | Live | Create Student: University student identifier | Enter validated bounded university student identifier; protected identity is absent from edit fields. | PENDING |
| F-160 | /admin/students | Live | Create Student: First name | Enter validated bounded first name; protected identity is absent from edit fields. | PENDING |
| F-161 | /admin/students | Live | Create Student: Last name | Enter validated bounded last name; protected identity is absent from edit fields. | PENDING |
| F-162 | /admin/students | Live | Create Student: University email | Enter validated bounded university email; protected identity is absent from edit fields. | PENDING |
| F-163 | /admin/students | Live | Create Student: Program | Enter validated bounded program; protected identity is absent from edit fields. | PENDING |
| F-164 | /admin/students | Live | Create Student: Education level | Enter validated bounded education level; protected identity is absent from edit fields. | PENDING |
| F-165 | /admin/students | Live | Create Student: Student status | Enter validated bounded student status; protected identity is absent from edit fields. | PENDING |
| F-166 | /admin/students | Live | Create Student record | Open confirmation review; no write until explicit confirmation. | PENDING |
| F-167 | /admin/students | Live | Cancel Create Student record | Dismiss review without mutation. | PENDING |
| F-168 | /admin/students | Live | Confirm Create Student record | Execute reviewed operation once; prevent duplicate submits; refresh affected queries after authoritative success. | PENDING |
| F-169 | /admin/students | Live | Close create Student form | Dismiss form without mutation. | PENDING |
| F-170 | /admin/students/:id | Live | Edit Student: Program | Enter validated bounded program; protected identity is absent from edit fields. | PENDING |
| F-171 | /admin/students/:id | Live | Edit Student: Education level | Enter validated bounded education level; protected identity is absent from edit fields. | PENDING |
| F-172 | /admin/students/:id | Live | Edit Student: Student status | Enter validated bounded student status; protected identity is absent from edit fields. | PENDING |
| F-173 | /admin/students/:id | Live | Update Student record | Open confirmation review; no write until explicit confirmation. | PENDING |
| F-174 | /admin/students/:id | Live | Cancel Update Student record | Dismiss review without mutation. | PENDING |
| F-175 | /admin/students/:id | Live | Confirm Update Student record | Execute reviewed operation once; prevent duplicate submits; refresh affected queries after authoritative success. | PENDING |
| F-176 | /admin/students/:id | Live | Close edit Student form | Dismiss form without mutation. | PENDING |
| F-177 | /admin/students/:id | Live | All Students | Navigate to /admin/students. | PENDING |
| F-178 | /admin/students/:id | Live | Student Passport | Navigate to /admin/students/:id/passport. | PENDING |
| F-179 | /admin/students/:id | Live | All Student credentials | Navigate to /admin/credentials?student_id=<selected uuid>. | PENDING |
| F-180 | /admin/students/:id | Live | Recent credential detail | Navigate to /admin/credentials/:id. | PENDING |
| F-181 | /admin/students/:id | Live | Credential Student record | Navigate to /admin/students/:id. | PENDING |
| F-182 | /admin/students/:id | Live | Edit academic profile | Toggle edit whitelist form; identity fields remain protected. | PENDING |
| F-183 | /admin/students/:id | Live | Select verified achievement | Select/deselect persisted VERIFIED own-Student achievement; selections persist across pages, maximum 256; show existing associations. | PENDING |
| F-184 | /admin/students/:id | Live | Previous records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-185 | /admin/students/:id | Live | Next records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-186 | /admin/students/:id | Live | Optional credential expiration | Select optional local datetime; convert to ISO timestamp on reviewed issuance. | PENDING |
| F-187 | /admin/students/:id | Live | Issue credential | Open confirmation review; no write until explicit confirmation. | PENDING |
| F-188 | /admin/students/:id | Live | Cancel Issue credential | Dismiss review without mutation. | PENDING |
| F-189 | /admin/students/:id | Live | Confirm Issue credential | Execute reviewed operation once; prevent duplicate submits; refresh affected queries after authoritative success. | PENDING |
| F-190 | /admin/students/:id | Live | Issued credential link | Open actual returned credential detail after authoritative issuance. | PENDING |
| F-191 | /admin/credentials | Live | Current validity / issuance state | Filter server rows by All, VALID, EXPIRED, REVOKED, INVALID or ISSUED; reset page. | PENDING |
| F-192 | /admin/credentials | Live | Student record UUID filter | Filter real credentials to selected Student UUID; invalid UUID gives safe error. | PENDING |
| F-193 | /admin/credentials | Live | Credential detail link | Open /admin/credentials/:id for the selected canonical UUID. | PENDING |
| F-194 | /admin/credentials | Live | Student record link | Open linked /admin/students/:id without disclosing data outside existing grant. | PENDING |
| F-195 | /admin/credentials | Live | Previous records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-196 | /admin/credentials | Live | Next records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-197 | /admin/credentials/:id | Live | Credential self detail | Open current credential detail. | PENDING |
| F-198 | /admin/credentials/:id | Live | Student record | Open selected credential owner Student record. | PENDING |
| F-199 | /admin/credentials/:id | Live | Public verification | Open public credential reference form; no fabricated result. | PENDING |
| F-200 | /admin/credentials/:id | Live | Student Passport | Open selected Student Passport route. | PENDING |
| F-201 | /admin/credentials/:id | Live | Revocation reason | Enter nonempty bounded reason (maximum 2000) for actual credential revocation. | PENDING |
| F-202 | /admin/credentials/:id | Live | Revoke credential | Open confirmation review; no write until explicit confirmation. | PENDING |
| F-203 | /admin/credentials/:id | Live | Cancel Revoke credential | Dismiss review without mutation. | PENDING |
| F-204 | /admin/credentials/:id | Live | Confirm Revoke credential | Execute reviewed operation once; prevent duplicate submits; refresh affected queries after authoritative success. | PENDING |
| F-205 | /admin/credentials/:id | Live | Previous records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-206 | /admin/credentials/:id | Live | Next records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-207 | /admin/skills | Live | Search skill/code/category/description | Filter current returned server page only; display explicit limitation; no catalog writes. | PENDING |
| F-208 | /admin/skills | Live | Previous records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-209 | /admin/skills | Live | Next records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-210 | /admin/course-mappings | Live | Search activity or skill code | Filter existing course-mapping projection by course name, ID or recognized skill codes; no policy mutation. | PENDING |
| F-211 | /admin/audit-logs | Live | Credential lifecycle history | Navigate to /admin/credentials under the separate required grant. General security audit API remains unavailable. | PENDING |
| F-212 | /admin/audit-logs | Live | Persisted simulated Classroom events | Navigate to /admin/classroom-sync under the separate required grant. General security audit API remains unavailable. | PENDING |
| F-213 | /admin/audit-logs | Live | Persisted import history and errors | Navigate to /admin/imports under the separate required grant. General security audit API remains unavailable. | PENDING |
| F-214 | /admin/students/:id/passport, /admin/passports/preview | Live | Student record | Navigate to associated Student detail. | PENDING |
| F-215 | /admin/students/:id/passport, /admin/passports/preview | Live | Open Passport public reference | Select returned Passport through ?passport=<internal uuid>; never arbitrary external URL. | PENDING |
| F-216 | /admin/students/:id/passport, /admin/passports/preview | Live | Current issued version | Reset version selection to currently returned latest issued snapshot. | PENDING |
| F-217 | /admin/students/:id/passport, /admin/passports/preview | Live | Inspect version N | Select exact immutable returned issued snapshot without changing current official version. | PENDING |
| F-218 | /admin/students/:id/passport, /admin/passports/preview | Live | Previous passports page | Load adjacent bounded passports page; disable at boundary; clear selected Passport when list page changes. | PENDING |
| F-219 | /admin/students/:id/passport, /admin/passports/preview | Live | Next passports page | Load adjacent bounded passports page; disable at boundary; clear selected Passport when list page changes. | PENDING |
| F-220 | /admin/students/:id/passport, /admin/passports/preview | Live | Previous issued versions page | Load adjacent bounded issued versions page; disable at boundary; clear selected Passport when list page changes. | PENDING |
| F-221 | /admin/students/:id/passport, /admin/passports/preview | Live | Next issued versions page | Load adjacent bounded issued versions page; disable at boundary; clear selected Passport when list page changes. | PENDING |
| F-222 | /admin/students/:id/passport, /admin/passports/preview | Live | Retry passports records | Retry exact failed authorized read with safe errors and cooldown. | PENDING |
| F-223 | /admin/students/:id/passport, /admin/passports/preview | Live | Retry versions records | Retry exact failed authorized read with safe errors and cooldown. | PENDING |
| F-224 | /admin/students/:id/passport, /admin/passports/preview | Live | Retry pdf status records | Retry exact failed authorized read with safe errors and cooldown. | PENDING |
| F-225 | /admin/students/:id/passport, /admin/passports/preview | Live | Download registered PDF | Execute explicitly requested operation once; pending state prevents duplicate submission. | PENDING |
| F-226 | /admin/students/:id/passport, /admin/passports/preview | Live | Generate Passport PDF | Open confirmation review; no write until explicit confirmation. | PENDING |
| F-227 | /admin/students/:id/passport, /admin/passports/preview | Live | Cancel Generate Passport PDF | Dismiss review without mutation. | PENDING |
| F-228 | /admin/students/:id/passport, /admin/passports/preview | Live | Confirm Generate Passport PDF | Execute reviewed operation once; prevent duplicate submits; refresh affected queries after authoritative success. | PENDING |
| F-229 | /admin/students/:id/passport, /admin/passports/preview | Live | Retry PDF generation | Open confirmation review; no write until explicit confirmation. | PENDING |
| F-230 | /admin/students/:id/passport, /admin/passports/preview | Live | Cancel Retry PDF generation | Dismiss review without mutation. | PENDING |
| F-231 | /admin/students/:id/passport, /admin/passports/preview | Live | Confirm Retry PDF generation | Execute reviewed operation once; prevent duplicate submits; refresh affected queries after authoritative success. | PENDING |
| F-232 | /admin/dashboard | Demo | Import Activity Records | Navigate to /admin/imports; all totals/activity are explicitly synthetic. | PENDING |
| F-233 | /admin/dashboard | Demo | Review Credentials | Navigate to /admin/credentials; all totals/activity are explicitly synthetic. | PENDING |
| F-234 | /admin/dashboard | Demo | View Students | Navigate to /admin/students; all totals/activity are explicitly synthetic. | PENDING |
| F-235 | /admin/dashboard | Demo | View Audit Logs | Navigate to /admin/audit-logs; all totals/activity are explicitly synthetic. | PENDING |
| F-236 | /admin/students | Demo | Program filter | Filter synthetic Students by selected program; all option clears filter. | PENDING |
| F-237 | /admin/students | Demo | Table search | Search text across displayed column values; reset pagination; no persistence. | PENDING |
| F-238 | /admin/students | Demo | Table status filter | Filter synthetic rows by listed states or All; reset pagination. | PENDING |
| F-239 | /admin/students | Demo | Sort by Student | Sort synthetic rows by Student ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-240 | /admin/students | Demo | Sort by Email | Sort synthetic rows by Email ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-241 | /admin/students | Demo | Sort by Program | Sort synthetic rows by Program ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-242 | /admin/students | Demo | Sort by Skills | Sort synthetic rows by Skills ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-243 | /admin/students | Demo | Sort by Credentials | Sort synthetic rows by Credentials ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-244 | /admin/students | Demo | Sort by Passport status | Sort synthetic rows by Passport status ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-245 | /admin/students | Demo | Previous records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-246 | /admin/students | Demo | Next records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-247 | /admin/students | Demo | Student name link | Open selected synthetic /admin/students/:id. | PENDING |
| F-248 | /admin/students/:id | Demo | Back to Students | Navigate /admin/students; available in missing-record state too. | PENDING |
| F-249 | /admin/students/:id | Demo | Passport preview | Open synthetic Student Passport preview. | PENDING |
| F-250 | /admin/students/:id | Demo | Supporting credential link | Open selected synthetic credential detail. | PENDING |
| F-251 | /admin/credentials | Demo | Table search | Search text across displayed column values; reset pagination; no persistence. | PENDING |
| F-252 | /admin/credentials | Demo | Table status filter | Filter synthetic rows by listed states or All; reset pagination. | PENDING |
| F-253 | /admin/credentials | Demo | Sort by Title | Sort synthetic rows by Title ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-254 | /admin/credentials | Demo | Sort by Student | Sort synthetic rows by Student ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-255 | /admin/credentials | Demo | Sort by Issuer | Sort synthetic rows by Issuer ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-256 | /admin/credentials | Demo | Sort by Status | Sort synthetic rows by Status ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-257 | /admin/credentials | Demo | Previous records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-258 | /admin/credentials | Demo | Next records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-259 | /admin/credentials | Demo | Credential title link | Navigate to synthetic credential detail. | PENDING |
| F-260 | /admin/credentials | Demo | Issue credential - disabled | Remain disabled; no fake official issuance. | PENDING |
| F-261 | /admin/credentials/:id | Demo | Back to credentials | Navigate to synthetic credential directory, including missing-record state. | PENDING |
| F-262 | /admin/credentials/:id | Demo | Student link | Navigate to corresponding synthetic Student record. | PENDING |
| F-263 | /admin/credentials/:id | Demo | Revoke credential - disabled | Remain disabled in Demo regardless of synthetic validity; no official revocation. | PENDING |
| F-264 | /admin/audit-logs | Demo | Table search | Search text across displayed column values; reset pagination; no persistence. | PENDING |
| F-265 | /admin/audit-logs | Demo | Sort by Timestamp | Sort synthetic rows by Timestamp ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-266 | /admin/audit-logs | Demo | Sort by Actor | Sort synthetic rows by Actor ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-267 | /admin/audit-logs | Demo | Sort by Action | Sort synthetic rows by Action ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-268 | /admin/audit-logs | Demo | Sort by Affected record | Sort synthetic rows by Affected record ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-269 | /admin/audit-logs | Demo | Previous records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-270 | /admin/audit-logs | Demo | Next records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-271 | /admin/skills | Demo | Search catalog | Filter categories by own name/ID, matching descendant name/code/description; preserve full tree for matching ancestors. | PENDING |
| F-272 | /admin/skills | Demo | Add category | Open new local category draft dialog. | PENDING |
| F-273 | /admin/skills | Demo | Edit category | Open existing local category name edit; preserve stable ID and relationships. | PENDING |
| F-274 | /admin/skills | Demo | Add subcategory to category | Open local subcategory draft with selected category parent. | PENDING |
| F-275 | /admin/skills | Demo | Expand/collapse subcategory | Toggle recursive synthetic hierarchy disclosure. | PENDING |
| F-276 | /admin/skills | Demo | Edit subcategory | Open local subcategory name edit; preserve stable ID and parent. | PENDING |
| F-277 | /admin/skills | Demo | Add skill | Open local skill draft under selected subcategory. | PENDING |
| F-278 | /admin/skills | Demo | Add nested subcategory | Open local subcategory draft under selected subcategory. | PENDING |
| F-279 | /admin/skills | Demo | Edit skill | Open local skill name/description edit; save sets draft and invalidates demo mapping approval. | PENDING |
| F-280 | /admin/skills | Demo | Name | Enter 2-100 character trimmed name; prevent duplicate same-kind names. | PENDING |
| F-281 | /admin/skills | Demo | Stable ID (read-only) | Display unchanged stable identifier; cannot edit. | PENDING |
| F-282 | /admin/skills | Demo | Parent selector | Select existing category/subcategory for creation; editing parent stays disabled. | PENDING |
| F-283 | /admin/skills | Demo | Skill description | Enter up to 500 character description. | PENDING |
| F-284 | /admin/skills | Demo | Cancel catalog dialog | Dismiss unsaved draft without mutation. | PENDING |
| F-285 | /admin/skills | Demo | Save catalog draft | Validate and update local in-memory tree only; preserve IDs/parents; draft skills cannot become approved. | PENDING |
| F-286 | /admin/course-mappings | Demo | Table search | Search text across displayed column values; reset pagination; no persistence. | PENDING |
| F-287 | /admin/course-mappings | Demo | Table status filter | Filter synthetic rows by listed states or All; reset pagination. | PENDING |
| F-288 | /admin/course-mappings | Demo | Sort by Course | Sort synthetic rows by Course ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-289 | /admin/course-mappings | Demo | Sort by Approved course | Sort synthetic rows by Approved course ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-290 | /admin/course-mappings | Demo | Sort by Skills | Sort synthetic rows by Skills ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-291 | /admin/course-mappings | Demo | Sort by Mapping status | Sort synthetic rows by Mapping status ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-292 | /admin/course-mappings | Demo | Sort by Approval | Sort synthetic rows by Approval ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-293 | /admin/course-mappings | Demo | Sort by Actions | Sort synthetic rows by Actions ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-294 | /admin/course-mappings | Demo | Previous records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-295 | /admin/course-mappings | Demo | Next records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-296 | /admin/course-mappings | Demo | Edit mapping | Open local mapping draft only for approved synthetic course; unapproved courses disabled. | PENDING |
| F-297 | /admin/course-mappings | Demo | Select approved skill | Toggle existing approved synthetic skill; no draft skill selectable. | PENDING |
| F-298 | /admin/course-mappings | Demo | Cancel mapping dialog | Discard unsaved selection. | PENDING |
| F-299 | /admin/course-mappings | Demo | Save mapping draft | Require nonempty unique approved skills; save in memory as draft and clear demo approval metadata. | PENDING |
| F-300 | /admin/skills, /admin/course-mappings, /admin/classroom-sync | Demo | Dialog close icon | Close currently open native modal without applying unsaved data. | PENDING |
| F-301 | /admin/skills, /admin/course-mappings, /admin/classroom-sync | Demo | Escape closes modal | Native dialog cancel closes modal and restores usable page focus. | PENDING |
| F-302 | /admin/classroom-sync | Demo | Table search | Search text across displayed column values; reset pagination; no persistence. | PENDING |
| F-303 | /admin/classroom-sync | Demo | Table status filter | Filter synthetic rows by listed states or All; reset pagination. | PENDING |
| F-304 | /admin/classroom-sync | Demo | Sort by Event | Sort synthetic rows by Event ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-305 | /admin/classroom-sync | Demo | Sort by Course | Sort synthetic rows by Course ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-306 | /admin/classroom-sync | Demo | Sort by Timestamp | Sort synthetic rows by Timestamp ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-307 | /admin/classroom-sync | Demo | Sort by Status | Sort synthetic rows by Status ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-308 | /admin/classroom-sync | Demo | Sort by Attempts | Sort synthetic rows by Attempts ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-309 | /admin/classroom-sync | Demo | Sort by Failure | Sort synthetic rows by Failure ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-310 | /admin/classroom-sync | Demo | Sort by Actions | Sort synthetic rows by Actions ascending; repeat toggles descending; update aria-sort and reset page. | PENDING |
| F-311 | /admin/classroom-sync | Demo | Previous records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-312 | /admin/classroom-sync | Demo | Next records page | Load adjacent bounded page using fixed endpoint and page number; disable at boundary. | PENDING |
| F-313 | /admin/classroom-sync | Demo | Preview event | Open read-only fictional event/student/proposed-skills modal; preview never syncs. | PENDING |
| F-314 | /admin/classroom-sync | Demo | Retry sync event - disabled | Remain disabled; no official mutation in Demo; non-failed rows also disabled. | PENDING |
| F-315 | /admin/classroom-sync | Live | Retry completion-preview records | Refetch controlled simulated provider completion projection. | PENDING |
| F-316 | /admin/classroom-sync | Live | Preview sync (dry run) | Execute explicitly requested operation once; pending state prevents duplicate submission. | PENDING |
| F-317 | /admin/classroom-sync | Live | Synchronize simulated completions | Open confirmation review; no write until explicit confirmation. | PENDING |
| F-318 | /admin/classroom-sync | Live | Cancel Synchronize simulated completions | Dismiss review without mutation. | PENDING |
| F-319 | /admin/classroom-sync | Live | Confirm Synchronize simulated completions | Execute reviewed operation once; prevent duplicate submits; refresh affected queries after authoritative success. | PENDING |
| F-320 | /admin/classroom-sync | Live | Refresh sync history | Refetch persisted simulation history without replaying source events. | PENDING |
| F-321 | /admin/classroom-sync | Live | Retry history records | Retry failed sanitized persisted events read. | PENDING |
| F-322 | /admin/classroom-sync | Live | Previous history | Load bounded previous cursor history using fixed endpoint; disable when absent. | PENDING |
| F-323 | /admin/classroom-sync | Live | Next history | Load bounded next cursor history using fixed endpoint; disable when absent. | PENDING |
| F-324 | /admin/classroom-sync | Live | Retry event <source event id> | Open confirmation review; no write until explicit confirmation. | PENDING |
| F-325 | /admin/classroom-sync | Live | Cancel Retry event <source event id> | Dismiss review without mutation. | PENDING |
| F-326 | /admin/classroom-sync | Live | Confirm Retry event <source event id> | Execute reviewed operation once; prevent duplicate submits; refresh affected queries after authoritative success. | PENDING |
| F-327 | /verify | Live and Demo | Reference lookup | Navigate to /verify/reference anonymously; embedded forms also remain available. | PENDING |
| F-328 | /verify | Live and Demo | Verify a PDF | Navigate to /verify/upload anonymously; embedded forms also remain available. | PENDING |
| F-329 | /verify, /verify/reference, /verify/qr, /verify/qr/:reference | Live and Demo | Verification reference input | Enter one printed Passport/version reference or kind-specific direct-link credential; normalize public references, reject private identifiers/unsafe formats; no request until submit. | PENDING |
| F-330 | /verify, /verify/reference, /verify/qr, /verify/qr/:reference | Live and Demo | Check reference / Enter form submit | Validate then make one anonymous method-bound registry lookup; show loading/cancel; present authoritative privacy-safe outcome; reject forged URL result. | PENDING |
| F-331 | /verify, /verify/reference, /verify/qr, /verify/qr/:reference | Live and Demo | Cancel reference request | Abort pending request; show canceled with no authenticity conclusion; late responses ignored. | PENDING |
| F-332 | /verify/reference | Live and Demo | Back to verification | Navigate /verify without preserving private upload data. | PENDING |
| F-333 | /verify/qr | Live and Demo | Back to verification | Navigate /verify without preserving private upload data. | PENDING |
| F-334 | /verify/qr/:reference | Live and Demo | Back to verification | Navigate /verify without preserving private upload data. | PENDING |
| F-335 | /verify/upload | Live and Demo | Back to verification | Navigate /verify without preserving private upload data. | PENDING |
| F-336 | /verify, /verify/upload | Live and Demo | Choose PDF / file input | Select exactly one nonempty .pdf, optional MIME application/pdf, maximum 5 MiB; keep file only in memory. | PENDING |
| F-337 | /verify, /verify/upload | Live and Demo | Drop PDF | Accept valid single dropped file; reject wrong type/size/multiple; prevent page navigation; disabled while pending. | PENDING |
| F-338 | /verify, /verify/upload | Live and Demo | Remove file | Clear file selection, native input and local validation errors; no request. | PENDING |
| F-339 | /verify, /verify/upload | Live and Demo | Submit PDF for verification / form submit | Send actual bytes as anonymous standard multipart named passport.pdf; no local authenticity inference; show authoritative outcome. | PENDING |
| F-340 | /verify, /verify/upload | Live and Demo | Cancel PDF request | Abort upload/request; do not show a verification verdict for canceled work. | PENDING |
| F-341 | /verify/* | Live and Demo | Start a new check | Navigate /verify; empty/reload/result/failure states never restore success from URL/storage. | PENDING |
| F-342 | /verify/* | Live and Demo | Retry verification | Navigate to safe original reference/form retry path, respect cooldown; no automatic write/lookup replay. | PENDING |
| F-343 | /verify/* | Live and Demo | Invalid QR/link manual lookup | Navigate /verify/reference when link malformed/missing/duplicate/conflicting. | PENDING |
| F-344 | /verify/* | Live and Demo | Unknown verification page back link | Show verification-not-found and navigate /verify. | PENDING |
| I-001 | /admin/imports | Demo | Excel workbook source switch | Show illustrative local completion-triple workbook preview, without imports | PENDING |
| I-002 | /admin/imports | Demo | Google Sheets source switch | Show demo-only Sheets URL explanation and disabled remote request | PENDING |
| I-003 | /admin/imports | Demo | Choose .xlsx file | Select a local nonempty .xlsx <=5 MiB; clear old preview/error | PENDING |
| I-004 | /admin/imports | Demo | Validate local workbook / form keyboard submission | Read first worksheet; require exactly student_id/course_id/skill_id; validate known demo student, approved course/skill mapping, required cells, duplicates and <=1000 rows | PENDING |
| I-005 | /admin/imports | Demo | Google Sheets URL input | Accept local URL input; preserve no provider credentials | PENDING |
| I-006 | /admin/imports | Demo | Request Sheets preview (disabled) | Keep remote provider access unavailable in Demo | PENDING |
| I-007 | /admin/imports | Demo | Search local validation preview | Filter local preview across all displayed columns; reset page | PENDING |
| I-008 | /admin/imports | Demo | Sort local preview by Row | Sort local rows ascending then descending by selected column; reset page | PENDING |
| I-009 | /admin/imports | Demo | Sort local preview by student_id | Sort local rows ascending then descending by selected column; reset page | PENDING |
| I-010 | /admin/imports | Demo | Sort local preview by course_id | Sort local rows ascending then descending by selected column; reset page | PENDING |
| I-011 | /admin/imports | Demo | Sort local preview by skill_id | Sort local rows ascending then descending by selected column; reset page | PENDING |
| I-012 | /admin/imports | Demo | Sort local preview by Validation | Sort local rows ascending then descending by selected column; reset page | PENDING |
| I-013 | /admin/imports | Demo | Previous local preview page | Page eight filtered local rows backward; disable at first page | PENDING |
| I-014 | /admin/imports | Demo | Next local preview page | Page eight filtered local rows forward; disable at last page | PENDING |
| I-015 | /admin/imports | Demo | Request import (disabled) | Never commit illustrative workbook rows as official evidence | PENDING |
| I-016 | /admin/imports | Demo | Search demo import history | Filter illustrative source/timestamp/status/errors; reset page | PENDING |
| I-017 | /admin/imports | Demo | Filter demo import history by status | Select all, failed or pending illustrative history; reset page | PENDING |
| I-018 | /admin/imports | Demo | Sort demo import history by Source | Sort illustrative history ascending/descending by selected column; reset page | PENDING |
| I-019 | /admin/imports | Demo | Sort demo import history by Timestamp | Sort illustrative history ascending/descending by selected column; reset page | PENDING |
| I-020 | /admin/imports | Demo | Sort demo import history by Status | Sort illustrative history ascending/descending by selected column; reset page | PENDING |
| I-021 | /admin/imports | Demo | Sort demo import history by Errors | Sort illustrative history ascending/descending by selected column; reset page | PENDING |
| I-022 | /admin/imports | Demo | Previous demo import history page | Move backward through eight-row filtered demo history; disable at boundary | PENDING |
| I-023 | /admin/imports | Demo | Next demo import history page | Move forward through eight-row filtered demo history; disable at boundary | PENDING |
| I-024 | /admin/imports | Live | Approved source dropdown | Choose approved Excel or server-configured Google source; clear private selected profile/file/preview | PENDING |
| I-025 | /admin/imports | Live | Authorized import profile dropdown | Choose enabled source-matching versioned mapping profile from current page; clear private file/preview | PENDING |
| I-026 | /admin/imports | Live | Previous approved profiles page | Load previous numbered 50-profile page; clear selection/preview | PENDING |
| I-027 | /admin/imports | Live | Next approved profiles page | Load next numbered 50-profile page; clear selection/preview | PENDING |
| I-028 | /admin/imports | Live | Refresh approved profiles | Refetch enabled profiles and clear selected profile/file/preview | PENDING |
| I-029 | /admin/imports | Live | Retry unavailable approved profiles | Explicitly refetch unavailable profile query after Retry-After; never fallback to Demo | PENDING |
| I-030 | /admin/imports | Live | Approved workbook file input | Keep selected .xlsx <=5 MiB in memory; clear previous preview; wrong file leaves preview disabled | PENDING |
| I-031 | /admin/imports | Live | Preview incoming Excel records | Submit exactly approved profile ID + workbook; show server-derived original mapping/row classifications | PENDING |
| I-032 | /admin/imports | Live | Preview incoming Google records | Read configured approved target via profile ID only; show server-derived snapshot and classifications | PENDING |
| I-033 | /admin/imports | Live | Expand/collapse row validation details | Toggle individual server row status/code/message list without side effects | PENDING |
| I-034 | /admin/imports | Live | Reviewed snapshot confirmation checkbox | Require deliberate review; enable only READY/FAILED unexpired preview with eligible rows; clear on submit/source/profile change | PENDING |
| I-035 | /admin/imports | Live | Confirm reviewed import | POST confirm:true and exact reviewed digest; execute saved valid records only; no automatic POST retry | PENDING |
| I-036 | /admin/imports | Live | Refresh preview outcome | Fetch creator-owned saved snapshot and persisted result; do not confirm or fetch/import newer remote snapshot | PENDING |
| I-037 | /admin/imports | Live | Excel workbook completion-source switch | Show legacy seven-column completion-evidence import below awarded-skill workflow | PENDING |
| I-038 | /admin/imports | Live | Configured Google Sheets completion-source switch | Show legacy server-configured Completions worksheet import; no URL entry | PENDING |
| I-039 | /admin/imports | Live | Completion workbook upload | Choose <=5 MiB nonempty .xlsx; show first ten rows of local seven-column schema; clear prior selection/outcome on change | PENDING |
| I-040 | /admin/imports | Live | Open Import Excel evidence confirmation | Open review panel before calling existing immediate completion import; selected local file required | PENDING |
| I-041 | /admin/imports | Live | Cancel Import Excel evidence | Close review panel without mutation | PENDING |
| I-042 | /admin/imports | Live | Confirm Import Excel evidence | Import original selected workbook active worksheet using approved BTU_EXCEL completion policy | PENDING |
| I-043 | /admin/imports | Live | Open Import configured Google Sheet confirmation | Review legacy configured Completions import; no client source/URL | PENDING |
| I-044 | /admin/imports | Live | Cancel Import configured Google Sheet | Close review panel without provider call/mutation | PENDING |
| I-045 | /admin/imports | Live | Confirm Import configured Google Sheet | Read server-configured sheet and process approved completion evidence using existing strict validator | PENDING |
| I-046 | /admin/imports | Live | Refresh import history | Refetch current persisted ImportRun page, including partial/failed runs | PENDING |
| I-047 | /admin/imports | Live | Retry unavailable import history | Explicitly retry safe read after request failure/Retry-After | PENDING |
| I-048 | /admin/imports | Live | Previous import history page | Navigate previous persisted cursor page without fetching arbitrary server URLs | PENDING |
| I-049 | /admin/imports | Live | Next import history page | Navigate next persisted cursor page without fetching arbitrary server URLs | PENDING |
| I-050 | /admin/imports | Live | Inspect/collapse import events | Show/hide saved completion inbox events belonging to selected import run; award receipt UUIDs are not completion events | PENDING |
| I-051 | /admin/imports | Live | Retry unavailable import events | Explicitly refetch safe run event read after error/Retry-After | PENDING |
| I-052 | /admin/imports | Live | Previous import events page | Navigate saved run event cursor backward | PENDING |
| I-053 | /admin/imports | Live | Next import events page | Navigate saved run event cursor forward | PENDING |
| I-054 | /admin/imports | Live | Open Retry import event confirmation | Review existing FAILED retryable completion event with attempts <5; accept no replacement evidence | PENDING |
| I-055 | /admin/imports | Live | Cancel Retry import event | Cancel replay without mutation | PENDING |
| I-056 | /admin/imports | Live | Confirm Retry import event | Replay persisted event payload through existing mapping/source/issuer guards and bounded idempotency; refresh linked history | PENDING |
| I-057 | /admin/imports | Live | Inspect Student achievements and credentials link | Navigate to /admin/students; target separately requires view_student_records | PENDING |
