#!/bin/sh
set -eu
python -m app.bootstrap
if [ "${1:-api}" = "worker" ]; then
  shift
  exec procrastinate --app=app.jobs.procrastinate_app worker --concurrency=2 "$@"
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8765
