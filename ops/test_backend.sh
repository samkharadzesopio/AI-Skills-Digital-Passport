#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Provision a fresh owned cluster; never adopt a development/Neon database.
passport_python="${PASSPORT_PYTHON:-python}"
"$passport_python" ops/run_isolated_tests.py --backend
git diff --check
