#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mode="${1:-demo}"
command -v docker >/dev/null || { echo 'Docker is required' >&2; exit 1; }
docker compose version >/dev/null
args=(-f "$ROOT/docker-compose.yaml")
if [[ -f "$ROOT/.env" ]]; then args=(--env-file "$ROOT/.env" "${args[@]}"); fi
if [[ "$mode" == production ]]; then
  [[ -f "$ROOT/.env" ]] || { echo 'Run init_env.py --mode production first' >&2; exit 1; }
  args+=(-f "$ROOT/docker-compose.production.yaml")
  docker network inspect campus-inference >/dev/null 2>&1 || docker network create campus-inference >/dev/null
elif [[ "$mode" != demo ]]; then
  echo 'Usage: bash deployment/start.sh [demo|production]' >&2; exit 2
fi
# Quiet validation avoids printing interpolated credentials.
docker compose "${args[@]}" config --quiet
docker compose "${args[@]}" up -d --build
