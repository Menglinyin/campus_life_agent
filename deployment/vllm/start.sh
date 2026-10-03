#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$ROOT/../.env" ]] || { echo 'Run deployment/init_env.py --mode production first' >&2; exit 1; }
bash "$ROOT/check_gpu.sh"
docker compose version >/dev/null
docker network inspect campus-inference >/dev/null 2>&1 || docker network create campus-inference >/dev/null
# Model check_model.py is an explicit preflight step described in README, not automatic env sourcing.
docker compose --env-file "$ROOT/../.env" -f "$ROOT/docker-compose.yaml" config --quiet
docker compose --env-file "$ROOT/../.env" -f "$ROOT/docker-compose.yaml" up -d
