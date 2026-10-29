#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../backend"
: "${PORT:=10000}"
# Override only the loopback bind; retain the reviewed limits and private logs.
exec gunicorn --config ../ops/gunicorn.conf.py --bind "0.0.0.0:${PORT}" config.wsgi:application
