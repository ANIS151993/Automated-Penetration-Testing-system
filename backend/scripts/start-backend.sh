#!/usr/bin/env sh
set -eu

python -m app.core.migration_bootstrap
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
