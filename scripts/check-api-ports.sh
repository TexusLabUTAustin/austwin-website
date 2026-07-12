#!/usr/bin/env bash
# Fail fast if API ports are taken by a non-AusTwin service.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/ports.sh"

is_austwin_uvicorn() {
  local pid="$1"
  local cmd
  cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  echo "$cmd" | grep -qE 'uvicorn.*app\.main:app|app\.main:app'
}

kill_stale_listeners() {
  local port="$1"
  local pids
  pids="$(lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null || true)"
  [[ -z "$pids" ]] && return 0
  for pid in $pids; do
    if is_austwin_uvicorn "$pid"; then
      echo "Clearing stale AusTwin server on port ${port} (pid ${pid})" >&2
      kill "$pid" 2>/dev/null || true
      sleep 0.3
      if kill -0 "$pid" 2>/dev/null; then
        kill -9 "$pid" 2>/dev/null || true
      fi
    fi
  done
  sleep 0.4
}

check_port() {
  local port="$1"
  local expect_service="$2"
  local url="http://127.0.0.1:${port}/health"

  if ! lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    return 0
  fi

  local body=""
  if body="$(curl -sf --max-time 5 "$url" 2>/dev/null)"; then
    if echo "$body" | grep -q "\"service\":\"${expect_service}\""; then
      return 0
    fi
    kill_stale_listeners "$port"
    if body="$(curl -sf --max-time 5 "$url" 2>/dev/null)"; then
      if echo "$body" | grep -q "\"service\":\"${expect_service}\""; then
        return 0
      fi
    fi
    cat >&2 <<EOF

Port ${port} is in use by another app (not AusTwin ${expect_service}).

Health response: ${body}

Run: npm run stop
Or set alternate dev ports in .env (see .env.example), then npm start

EOF
    exit 1
  fi

  # Listener present but no health — often a hung previous npm start
  kill_stale_listeners "$port"
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    cat >&2 <<EOF

Port ${port} is in use but did not respond as AusTwin ${expect_service}.

Listeners:
$(lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)

Run: npm run stop
Or change dev ports in .env, then npm start

EOF
    exit 1
  fi
}

check_port "$CITYFORESIGHT_DEV_PORT" "cityforesight"
check_port "$URBANSENSE_DEV_PORT" "urbansense"
check_port "$CITYGUIDE_DEV_PORT" "cityguide"
check_port "$THERMALSCAPE_DEV_PORT" "thermalscape"
