#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
args=(-f "$ROOT/docker-compose.yaml")
if [[ -f "$ROOT/.env" ]]; then args=(--env-file "$ROOT/.env" "${args[@]}"); fi
# Synthetic importer is intentionally restricted to the demo deployment.
docker compose "${args[@]}" exec -T backend python data/generate.py --output data/local/generated --days 3
docker compose "${args[@]}" exec -T backend python data/import_data.py --business-dir data/local/generated --apply
docker compose "${args[@]}" restart backend
