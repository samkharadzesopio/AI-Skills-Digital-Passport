#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
passport_python="${PASSPORT_PYTHON:-python}"
"$passport_python" backend/manage.py test apps.api apps.integrations apps.skills apps.credentials apps.passports apps.students apps.accounts apps.verification --settings=apps.integrations.postgres_test_settings --verbosity=1
"$passport_python" backend/manage.py makemigrations --check --dry-run --settings=apps.integrations.postgres_test_settings
git diff --check
