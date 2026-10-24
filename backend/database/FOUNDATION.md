# Student and Skill migration foundation

Django migrations own `students` and `skills_catalog`. `schema.sql` is reference
documentation: do not execute it alongside migrations. The existing `0001_initial`
migrations remain unchanged, including PostgreSQL UUID defaults and timestamp
triggers. `students.0002_external_student_id_normalization` adds one check constraint.

Student UUIDs and external university IDs are separate. Model `save()` and
`full_clean()` trim surrounding whitespace from external IDs without changing case,
internal punctuation, or internal whitespace. Repository lookups remain exact.
Bulk operations and raw SQL bypass model normalization: callers must supply canonical
IDs or the database rejects them. No case-folding or university ID-format assumption
is introduced. The database boundary-whitespace check explicitly matches Python's
Unicode whitespace set instead of relying on PostgreSQL locale classification.

The new constraint deliberately does not rewrite existing data. If another database
already contains noncanonical IDs, review them and possible normalized collisions
before applying it; migration should fail rather than silently merge identities.

## Isolated PostgreSQL checks

Use a fresh, disposable local PostgreSQL cluster listening only on `127.0.0.1`, with
a dedicated `passport_test` role, a database named `foundation_test`, and a temporary
password. Never reuse the configured Neon connection or an existing shared cluster.
The role needs database-creation privileges for Django's disposable test database.

Set `FOUNDATION_TEST_PG_HOST=127.0.0.1`, `FOUNDATION_TEST_PG_PORT`, and
`FOUNDATION_TEST_PG_PASSWORD` in the local test process environment. The isolated
settings require those values, never load `.env`, and never use `DATABASE_URL`.
Verify `SHOW data_directory` points to the newly initialized temporary cluster
before applying migrations. From `backend`, using the project virtual environment:

```text
python manage.py check --settings=config.foundation_test_settings
python manage.py makemigrations --check --dry-run --settings=config.foundation_test_settings
python manage.py migrate --plan --settings=config.foundation_test_settings
python manage.py sqlmigrate students 0001 --settings=config.foundation_test_settings
python manage.py sqlmigrate students 0002 --settings=config.foundation_test_settings
python manage.py sqlmigrate skills 0001 --settings=config.foundation_test_settings
python manage.py migrate --settings=config.foundation_test_settings
python manage.py test apps.students apps.skills apps.integrations.tests apps.verification.tests --settings=config.foundation_test_settings --noinput
```

The dedicated test runner excludes exactly two legacy tests that execute the full
reference SQL. All other discovered tests run, including PostgreSQL concurrency
tests. `sqlmigrate` cannot display the existing `RunPython` operations: inspect their
source and verify the installed defaults/triggers after applying migrations locally.
Stop and discard the temporary cluster after testing.

Only Student and Skill are registered by this change. Authentication, permissions,
routes and future achievements, credentials, passports, blockchain and analysis
models remain outside this foundation. Coordinate account ownership and achievement
provenance contracts before implementing their later migrations.
