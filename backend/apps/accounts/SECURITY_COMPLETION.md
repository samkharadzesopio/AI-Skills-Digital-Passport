# Phase D security changes

Production login and password-reset requests now enqueue delivery-control records
for both known and unknown valid BTU addresses. No account-existence query or SMTP
occurs on those HTTP paths. Existing per-IP/per-address limits and cooldowns remain;
the queue adds independent admission budgets. Malformed addresses may have different
processing times; no claim of constant-time HTTP processing is made.

DeferredMail stores the normalized recipient, purpose, originating IP, request times,
lease and retry state. It never stores plaintext OTPs, passwords, invitation tokens
or mail bodies. The worker generates codes through the existing services, sends
outside database transactions with a 10-second SMTP timeout, and activates login
challenges only after successful delivery. Original delivery/expiry/single-use and
session invalidation semantics remain. The queue is at-least-once, not exactly-once;
a worker crash can cause another email, but cannot bypass single-use verification.
The 60-second lease and three-attempt cap are recoverable; stale jobs expire after
five minutes. Unknown/inactive identities are completed silently without delivery.

Run `python manage.py deliver_auth_mail` frequently from a trusted process/scheduler
(e.g. every 5 seconds; at most 100 jobs/invocation). It is a bounded drain command,
not a daemon or installed scheduler. Requests will not deliver mail until a worker
runs. Test-only ACCOUNTS_ALLOW_TEST_EMAIL retains inline delivery for existing
locmem tests; it must remain false in production. Actual SMTP/network latency and
worker throughput have NOT been measured. Existing TLS, HTTPS, secure-cookie and
private-key configuration checks still apply. Email verification/invitations are
already authenticated operations and retain synchronous delivery with finite timeout.

SecurityAudit records actor, action, HMAC of the direct client IP, time, and response
status for mutating accounts/integration API actions, including permission denials.
Attempts are written before authorized execution; status zero indicates interruption
or an unhandled server error. No bodies, codes, passwords, exception strings or
profile data are retained. Audit insertion failure prevents action execution.
Records are application-controlled audit evidence, not tamper-proof against the
DB owner. Configure retention/access controls and backups through operator policy.
No-store headers protect authentication, admin and public-verification responses
from caching stale results or session data. No permissions were relaxed.

New migration accounts/0006 depends on accounts/0005_account_integrity_triggers.
It adds only delivery-control and audit tables. All earlier auth migrations and
Student/Credential/Passport schemas remain unchanged. Review before shared Neon.

Validation: full PostgreSQL regression suite passed 320 tests (existing runner
excludes two legacy schema comparisons). Production-mode queue tests exercise
request/worker separation, successful single-use login, failed delivery recovery,
unknown users, job expiry and last-lease recovery. Tests use synthetic identities.
Deployment workers, SMTP credentials, proxy limits and audit retention are operator
requirements; none were installed on production or applied to shared Neon.
