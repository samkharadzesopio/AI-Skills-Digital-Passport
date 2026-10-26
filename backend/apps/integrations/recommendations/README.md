# Personalized rule-based course recommendations

Implemented under apps/integrations/recommendations on branch
feature/rule-based-course-recommendations. This branch starts from the current
verification feature commit 50db374 (whose shared ancestor is integration f8057c5).
No merge, shared Neon migration, deployment or push is performed by this task.

## Mode and scope

The only production analyzer implemented is RuleBasedAnalyzer. Responses explicitly
say analysis_mode=RULE_BASED and every rationale has ai_assisted=false. There are
no external AI/HTTP calls, API-key requirements, new SDKs/dependencies or AI-generated
responses. Existing PostgreSQL/session security configuration is still needed to
run the backend; 'no AI API keys' does not mean the application has no secrets.
This feature recommends courses, not jobs, degree requirements or credential awards.

Files: contracts.py (immutable DTOs/interfaces), providers.py (local simulation and
catalog validation), profile.py (scoped PostgreSQL reads), analyzers.py (pure rules),
service.py (authoritative output validation/pathways), api.py (private API/filters/
rate limits), data/catalog.json and data/history.json, tests.py, test_api.py,
test_population.py, docs/examples.json. The sole existing routing edit is
apps/integrations/urls.py. No shared settings, models, migrations, trusted issuance
mappings or Student/Credential/Passport services were changed.

## Simulated academic provider

AcademicProvider.get_catalog returns immutable Course DTOs, with identifiers,
titles, descriptions, department/category, explicit competency-level learning
outcomes, hard prerequisite course IDs and skill codes, difficulty, optional
credits/suggested semester, interests and optional availability. The 24 invented
courses cover programming, software engineering, databases, AI, mathematics,
networking/OS, cybersecurity, cloud and data science. They are clearly labeled
SIMULATED_BTU_CATALOG; they are not official BTU course approvals or live enrollment.
One sample course is explicitly unavailable. Availability=None means unknown and
is reported as such, not invented as open enrollment.

AcademicProvider.get_completed_courses receives only the current Student's external
university ID, read from PostgreSQL. It returns deduplicated passed/completed catalog
IDs. The simulated history is indexed by that ID: the beginner and advanced sample
identities have declared histories; an unknown identity gets an empty history,
never a randomly assigned sample student. Stable provider JSON is cached/indexed
once; no private PostgreSQL learning profile or response is globally cached.

A replacement authenticated BTU adapter implements the same two methods, source and
disclaimer. It must validate external identities, deduplicate passed completions,
normalize catalog codes, bound input, verify TLS/use institution-controlled hosts,
use timeouts and provide accurate provenance. External I/O belongs in that adapter,
not in rules or database transactions. No live BTU API exists in this implementation.
Real provider data must use consistent identifiers/outcome mappings; descriptions
are data, never executable instructions. JSON text must be escaped normally by clients.

## Actual student profile and evidence

The current Student UUID is resolved through the existing authenticated ownership
helper. The service reads only that Student's external ID and verified achievements.
It also recognizes persisted completed-course IDs from the existing trusted
BTU_CLASSROOM/BTU_EXCEL/BTU_GOOGLE_SHEETS achievement receipts. Those events were
validated by the existing issuance/import pipeline. Unknown catalog IDs are reported
as unmapped; no title matching silently invents equivalence.

Three evidence groups remain distinct:

- verified_achievement_skills: PostgreSQL VerifiedAchievement status VERIFIED.
- passport_verified_skills: those achievements represented in the latest issued
  Passport through currently issued/unexpired credentials and an approved, trusted
  database issuer. Revoked/expired/untrusted credentials cannot populate this group.
- inferred_course_skills: outcomes of completed academic courses in the provider
  catalog. These are knowledge inferences, never newly verified achievements.

Revoking a credential does not erase the historical achievement/course record.
The response preserves that learning evidence while removing current Passport
certification. Interests are optional preferences, not claims of knowledge.
Learning readiness uses verified achievement and inferred course knowledge; it
never uses interests as skill evidence. Recommendations issue no achievements,
credentials, badges, Passport versions or academic records.

The profile reports mapped completed courses, each skill evidence group, missing
competencies among available catalog outcomes, and the highest completed catalog
level. Missing competencies describe learning opportunities, not mandatory degree
requirements. Suggested semesters belong to the simulated course metadata; no
student's official semester is guessed.

## Eligibility and scoring

Hard gates exclude completed/unavailable courses, courses with any missing required
course or competency, and courses whose outcomes are already fully known. Verified
skills do not waive explicit course prerequisites. Catalog duplicates, unknown
prerequisite IDs, invalid metadata and dependency cycles fail closed.

Default score weights total 100 and can be supplied through RuleBasedAnalyzer's
constructor by trusted server code:

| Factor | Weight | Structured rule |
|---|---:|---|
| New competencies | 35 | fraction of course outcomes not yet known |
| Progression | 20 | full weight for the next catalog level; half for other eligible levels |
| Foundation unlocks | 20 | newly eligible courses after this hypothetical completion, capped at two |
| Interest | 15 | explicit learning-direction tag match |
| Complement | 10 | known prerequisite/background competencies and completed prerequisites, capped at two |

These weights are transparent initial policy, not a statistically calibrated
probability. Ties sort by course ID. Titles never affect scores; text explains
already-established outcome/prerequisite links. Reasons cite actual completed
courses/relevant competencies, new outcomes and courses unlocked by completion.
They do not claim a model performed semantic analysis.

Pathways show at most three next-course plans with at most three conditional future
steps. Every future step must become eligible after the stated assumed completions;
no future knowledge is inserted into the student's real profile. Current unmet
requirements remain visible and FUTURE is distinct from READY. Pathways are bounded
linear possibilities, not exhaustive schedules or promises of enrollment.

## Secure API

GET /api/integrations/course-recommendations/

Requires an active, verified, linked Student session and the existing authoritative
User-to-Student resolver. Administrators, anonymous/unlinked/inactive accounts and
inactive or mismatched Student links fail closed. Student IDs are never accepted
from client filters. Responses contain no names, emails, account UUIDs or grades;
academic details are private to the authenticated Student.

Allowed query filters only: category, interest, difficulty, limit (1..10, default 5),
include_future_pathway (default true). Categories/difficulties/interests are explicit
enums in contracts.py. Duplicate/unknown parameters, student_id, analysis_mode or
API-key parameters are rejected. Source, mode, provenance, ranked recommendations,
profile, blocked courses, warnings and pathways use the same response shape for
future analyzers. Cache-Control:no-store prevents personal response caching.

Each ranked course supplies ID/title/department/category/difficulty, score, existing
competencies, related completed courses, potential new skills, missing prerequisites,
readiness, grounded reason/progression, learning outcomes, ai_assisted, source and
provider-supplied optional credits/semester/availability.

Operational rate limiting uses the existing PostgreSQL security counter table,
HMAC-namespaced per authenticated User, 30 requests/minute across workers. This is
the API's only write. Profile loading and recommendation generation are SELECT-only;
no new recommendation table exists. A pure read-only service test and an API test
separately prove this distinction. Existing gateway/global abuse controls remain
necessary; per-user limits are not a production concurrency certification.

## Replaceable analyzer, no LLM implementation

RecommendationAnalyzer.analyze(profile, catalog, options) returns Analysis containing
bounded catalog-ID/score/reason proposals and analysis_mode. RuleBasedAnalyzer is
the default, without an alternate configurable remote provider or hidden API path.
A later LLMAnalyzer may implement this interface without changing the API, provider,
frontend or database models. Only after actual model analysis may that implementation
return AI_ASSISTED. There is deliberately no placeholder LLMAnalyzer pretending to
make calls in this phase.

The service independently rechecks proposal IDs, uniqueness, finite scores, filters,
readiness and rationale size before generating authoritative metadata/pathways.
Invalid or unavailable injected analyzers fall back to the real deterministic engine,
with RULE_BASED plus a sanitized warning. Tests use fake *invalid analyzer objects*
to validate this boundary; no fake AI-generated recommendation is served in production.
Before enabling any future remote analyzer, it must also restrict eligible candidates,
minimize context, defend against instructions in provider text, verify factual rationale
citations, enforce network/output bounds and undergo privacy review. This is future
work, not a claimed current AI capability.

## Bounds, measurements and tests

Catalog <=200 courses, <=20 outcomes/course, bounded metadata; profile <=2,000 distinct
history/achievement rows. Missing catalog/provider failures return a sanitized 503.
Empty history gets honest foundation guidance plus a warning, not invented courses.
No SQL N+1 pattern: three profile queries with issuer policy configured, independent
of the university's total Student count. The existing authorization/throttle queries
are additional; API tests enforce a bounded budget and only security-counter writes.

Final combined run: 409 tests passed in 65.595 seconds (411 discovered; two existing legacy schema-SQL
comparison tests explicitly excluded). No concurrency tests skipped. No migration
drift and no new dependencies. Focused coverage includes differing learner levels,
verified/inferred evidence, revoked Passport membership, readiness, non-AI subjects,
redundancy, stable ranking, interests, pathways, cycles, provider replacement/failure,
invalid analyzer output, ownership, malformed filters and concurrent rate limiting.

On a local PostgreSQL fixture of 5,000 Students / 4,998 achievement rows, 30 sequential
service calls used exactly three queries each: median 33.604 ms, p95 45.451 ms in the
final combined run. A focused run measured 31.936/46.963 ms, illustrating variability.
These are service/test timings including query-capture overhead, not HTTP/Neon latency
or 5,000 concurrent-user capacity. Staging load/provider latency remain unmeasured.

Reproduce from repository root with the documented disposable loopback PostgreSQL:

```
PASSPORT_PYTHON=/absolute/path/to/python ./ops/test_backend.sh
```

Two computed synthetic examples, including scores/reasons/pathways and explicit
RULE_BASED mode, are in docs/examples.json. Beginner starts with Python Programming,
Version Control and Databases; the advanced context prioritizes Machine Learning,
Database Performance and Backend Engineering. They are generated by this engine,
not hand-authored AI responses. No API keys or environment variables were added.

Joint review: course/outcome mapping, initial scoring weights, source provenance and
UI interpretation of verified versus inferred knowledge. This branch contains the
prior public verification feature as its parent; coordinate integration order. Do not
apply shared Neon migrations, auto-deploy or push without the user's instruction.
