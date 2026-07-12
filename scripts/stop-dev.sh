#!/usr/bin/env bash
# Stop AusTwin dev API processes bound to configured ports.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/ports.sh"

PORTS=(
  "$CITYFORESIGHT_DEV_PORT"
  "$URBANSENSE_DEV_PORT"
  "$CITYGUIDE_DEV_PORT"
  "$THERMALSCAPE_DEV_PORT"
)

for port in "${PORTS[@]}"; do
  pids="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)"
  [[ -z "$pids" ]] && continue
  for pid in $pids; do
    cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    if echo "$cmd" | grep -qE 'uvicorn|app\.main'; then
      echo "Stopping port $port (pid $pid)" >&2
      kill "$pid" 2>/dev/null || true
      sleep 0.3
      if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
      fi
    fi
  done
done

sleep 0.5
echo "Dev API ports cleared."
