#!/bin/sh
set -e

# Only the API service runs migrations, so a concurrent restart of
# app-backend and worker (same image/entrypoint) can't race on Alembic.
case "$1" in
  uvicorn)
    alembic upgrade head
    ;;
esac

exec "$@"
