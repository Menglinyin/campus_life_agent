#!/usr/bin/env bash
set -euo pipefail
command -v nvidia-smi >/dev/null || { echo 'nvidia-smi is required on the Linux GPU host' >&2; exit 1; }
nvidia-smi --query-gpu=index,name,memory.total,memory.free,driver_version --format=csv
count="$(nvidia-smi --query-gpu=index --format=csv,noheader | wc -l)"
[[ "$count" -ge 2 ]] || { echo 'Tensor parallel size 2 requires two visible GPUs' >&2; exit 1; }
echo 'GPU inventory only; Docker GPU runtime, topology and AWQ kernels still need real validation.'
