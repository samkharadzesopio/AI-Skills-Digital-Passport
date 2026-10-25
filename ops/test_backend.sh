#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Combined test settings are loopback-only and never load production .env.
export FOUNDATION_TEST_PG_HOST="${FOUNDATION_TEST_PG_HOST:-127.0.0.1}"
export FOUNDATION_TEST_PG_PORT="${FOUNDATION_TEST_PG_PORT:-55432}"
export FOUNDATION_TEST_PG_PASSWORD="${FOUNDATION_TEST_PG_PASSWORD-}"
export AUTH_TEST_PG_PORT="${AUTH_TEST_PG_PORT:-$FOUNDATION_TEST_PG_PORT}"
passport_python="${PASSPORT_PYTHON:-python}"
"$passport_python" backend/manage.py test apps.api apps.integrations apps.skills apps.credentials apps.passports apps.students apps.accounts apps.verification --settings=apps.integrations.postgres_test_settings --verbosity=1
"$passport_python" backend/manage.py makemigrations --check --dry-run --settings=apps.integrations.postgres_test_settings
git diff --check
