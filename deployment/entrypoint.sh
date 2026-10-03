#!/usr/bin/env sh
set -eu
# Docker Compose provides CAMPUS_ values; avoid embedding secrets in images.
exec "$@"
