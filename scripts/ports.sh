#!/usr/bin/env bash
# Load dev API ports from repo-root .env (if present).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

export CITYFORESIGHT_DEV_PORT="${CITYFORESIGHT_DEV_PORT:-8000}"
export URBANSENSE_DEV_PORT="${URBANSENSE_DEV_PORT:-8001}"
export CITYGUIDE_DEV_PORT="${CITYGUIDE_DEV_PORT:-8002}"
