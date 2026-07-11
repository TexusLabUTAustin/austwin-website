#!/usr/bin/env bash
# Fail fast if API ports are taken by a non-AusTwin service.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/ports.sh"

check_port() {
  local port="$1"
  local expect_service="$2"
  local url="http://127.0.0.1:${port}/health"

  if ! lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    return 0
  fi

  local body=""
  if body="$(curl -sf --max-time 3 "$url" 2>/dev/null)"; then
    if echo "$body" | grep -q "\"service\":\"${expect_service}\""; then
      return 0
    fi
    cat >&2 <<EOF

Port ${port} is in use by another app (not AusTwin ${expect_service}).

Health response: ${body}

Free the port or set alternate dev ports in .env:
  CITYFORESIGHT_DEV_PORT=8010
  URBANSENSE_DEV_PORT=8011
  URBANSENSE_CITYFORESIGHT_URL=http://localhost:8010

Then restart: npm start

EOF
    exit 1
  fi

  cat >&2 <<EOF

Port ${port} is in use but did not respond as AusTwin ${expect_service}
(often Cursor or another tool is bound to localhost:${port}).

Listeners:
$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)

Free the port or set alternate dev ports in .env (see .env.example), then npm start

EOF
  exit 1
}

check_port "$CITYFORESIGHT_DEV_PORT" "cityforesight"
check_port "$URBANSENSE_DEV_PORT" "urbansense"
check_port "$CITYGUIDE_DEV_PORT" "cityguide"
