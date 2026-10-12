#!/bin/sh
# Alembic owns the schema, so the image must bring the database to head before
# the gateway accepts traffic; the application will refuse to start otherwise.
# `exec` replaces this shell with the CMD process, so uvicorn is PID 1 and
# receives SIGTERM directly instead of through a shell that ignores it.
set -e

alembic upgrade head
exec "$@"
