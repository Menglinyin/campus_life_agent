#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mode="${1:-demo}"
args=(-f "$ROOT/docker-compose.yaml")
if [[ -f "$ROOT/.env" ]]; then args=(--env-file "$ROOT/.env" "${args[@]}"); fi
if [[ "$mode" == production ]]; then args+=(-f "$ROOT/docker-compose.production.yaml");
elif [[ "$mode" != demo ]]; then echo 'Usage: stop.sh [demo|production]' >&2; exit 2; fi
# Preserve named volumes and their data; no --volumes option.
docker compose "${args[@]}" down
