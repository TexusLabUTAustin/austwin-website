#!/usr/bin/env bash
# Run a command inside the austwin conda env (active session or conda run).
set -euo pipefail

ENV_NAME="${AUSTWIN_CONDA_ENV:-austwin}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

run_in_env() {
  if [[ "${CONDA_DEFAULT_ENV:-}" == "$ENV_NAME" ]]; then
    exec "$@"
  fi

  if command -v conda &>/dev/null; then
    if conda env list | awk 'NR>2 {print $1}' | grep -qx "$ENV_NAME"; then
      exec conda run --no-capture-output -n "$ENV_NAME" "$@"
    fi
  fi

  cat >&2 <<EOF
AusTwin conda env '$ENV_NAME' is not available.

First-time setup:
  npm run setup
  conda activate $ENV_NAME
  npm start

EOF
  exit 1
}

run_in_env "$@"
