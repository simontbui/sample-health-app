#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
documents=${1:-200000}
if ! [[ $documents =~ ^[0-9]+$ ]] || (( documents < 4 || documents % 4 != 0 )); then
  echo 'Document count must be a positive multiple of 4 (default 200000).'; exit 1
fi
docker compose up -d --wait
exists=$(docker compose exec -T db psql -U bench -d docbench -Atc "SELECT count(*) FROM pg_namespace WHERE nspname='clinical'")
if [[ $exists != 0 ]]; then
  echo 'Existing clinical schema found; leaving all data unchanged. Run scripts/benchmark.sh.'
  exit 0
fi
for file in 01-schema.sql 02-seed.sql 03-indexes.sql 04-separated.sql; do
  docker compose exec -T db psql -X -U bench -d docbench -v ON_ERROR_STOP=1 -v documents="$documents" -f "/bench/$file"
done
docker compose exec -T db psql -X -U bench -d docbench -v ON_ERROR_STOP=1 -v documents="$documents" -f /bench/06-verify.sql
echo 'Ready: localhost:55432 / docbench / bench / local-bench-only'
