#!/usr/bin/env bash
# Run a project-local Postgres (no Docker) on :5433 using Homebrew's postgresql@17 + pgvector.
#   brew install postgresql@17 pgvector
set -euo pipefail
cd "$(dirname "$0")/.."
export LC_ALL=${LC_ALL:-en_US.UTF-8}
DATA=.pgdata
case "${1:-start}" in
  start)
    if [ ! -d "$DATA" ]; then
      initdb -D "$DATA" -U rag --auth=trust -E UTF8 >/dev/null
      pg_ctl -D "$DATA" -o "-p 5433 -k /tmp" -l "$DATA/server.log" start
      sleep 2
      createdb -h /tmp -p 5433 -U rag rag
      psql -h /tmp -p 5433 -U rag -d rag -c "CREATE EXTENSION IF NOT EXISTS vector;" >/dev/null
    else
      pg_ctl -D "$DATA" -o "-p 5433 -k /tmp" -l "$DATA/server.log" start
    fi ;;
  stop) pg_ctl -D "$DATA" stop ;;
  *) echo "usage: $0 [start|stop]"; exit 1 ;;
esac
