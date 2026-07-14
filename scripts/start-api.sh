#!/usr/bin/env bash
# Start CityForesight, UrbanSense, or CityGuide uvicorn on configured dev ports.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/ports.sh"

SERVICE="${1:?service name required (cityforesight|urbansense|cityguide|thermalscape)}"

case "$SERVICE" in
  cityforesight)
    cd "$ROOT/services/cityforesight"
    exec python -m uvicorn app.main:app --reload --host 0.0.0.0 --port "$CITYFORESIGHT_DEV_PORT"
    ;;
  urbansense)
    cd "$ROOT/services/urbansense"
    exec python -m uvicorn app.main:app --reload --host 0.0.0.0 --port "$URBANSENSE_DEV_PORT"
    ;;
  cityguide)
    cd "$ROOT/services/cityguide"
    exec python -m uvicorn app.main:app --reload --host 0.0.0.0 --port "$CITYGUIDE_DEV_PORT"
    ;;
  thermalscape)
    cd "$ROOT/services/thermalscape"
    exec python -m uvicorn app.main:app --reload --host 0.0.0.0 --port "$THERMALSCAPE_DEV_PORT"
    ;;
  *)
    echo "Unknown service: $SERVICE" >&2
    exit 1
    ;;
esac
