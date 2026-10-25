# Measured local verification/import observations

Run on 2026-10-25, Python 3.13.5, Django 6.1.2, local PostgreSQL 17, one cloud
execution machine. Harness: apps.integrations.postgres_test_settings, synthetic
records only. The combined regression run executed 379 tests successfully; 381 were
discovered and the existing runner explicitly excluded two legacy reference-SQL
comparison tests. No concurrency assertions were skipped. No migration drift.
The unmodified f8057c5 baseline first passed 365 tests.

Fixture at verification time: 5,000 Students and 5,000 Credentials, with valid
source achievements/links/lifecycle rows satisfying actual PostgreSQL constraints.
One fixture Passport/snapshot is used for repeated Passport lookup measurements;
this is not a claim of 5,000 populated Passport versions or concurrent users.
Bulk fixture setup is not measured as institutional service ingestion throughput.

Final combined-run observations:

| Check | Samples | Queries per call | Median | p95 |
|---|---:|---:|---:|---:|
| Credential verification, distributed public references | 100 | 1 | 1.802 ms | 3.000 ms |
| Passport reference verification, one populated snapshot | 100 | 2 | 4.783 ms | 6.959 ms |

Fixture construction: 3.576 s. PostgreSQL EXPLAIN ANALYZE confirmed an indexed
credential public-reference lookup after ANALYZE. Verification performed no domain
writes. Query assertions fail if these lookups regress into N+1 queries.

Twenty authorized Excel completion events against the population issued twenty
credentials in 2.117 s / 1,222 captured queries. Replaying those same events took
0.190 s and skipped all twenty, adding zero duplicate credentials. The query cost
is material (~61 queries/event in this local sample, including durable receipt,
transaction and lifecycle orchestration). Optimize only after profiling with the
actual provider/workload; batching must preserve the current per-event recovery
and audit boundaries. No transactions were weakened for benchmark numbers.

A separate focused measurement observed credential median/p95 1.821/4.202 ms,
Passport median/p95 4.458/8.752 ms, import 1.262 s and replay 0.160 s, illustrating
normal run-to-run variation. Measurements include Python test/query-capture
overhead and exclude HTTP, rate-limit counter costs, TLS, Neon network latency,
SMTP, Google APIs and PDF rendering. They are not end-to-end request SLA values.

PDF service tests now assert three bounded registry/status queries, versus the old
two integrity-only queries. The extra query adds current credential validity; raw
profile/snapshot/storage fields are no longer selected by the document repository.

Reproduce:

```
PASSPORT_PYTHON=/absolute/path/to/python ./ops/test_backend.sh
```

Or run apps.verification.test_performance with the same combined settings and the
loopback variables documented in INTEGRATION_REVIEW.md. Results print as one
LOCAL_PERFORMANCE JSON record; no raw rows, credentials or user data are printed.

This validates correctness against a 5,000-student fixture, not production capacity
or 5,000-user concurrency. Staging still needs realistic Passport sizes, a real
network/gateway, contention tests, provider latency and an agreed load/SLA target.
