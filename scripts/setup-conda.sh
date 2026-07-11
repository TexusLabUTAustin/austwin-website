#!/usr/bin/env bash
# Create or update the austwin conda environment and install Python packages editable.
set -euo pipefail

ENV_NAME="${AUSTWIN_CONDA_ENV:-austwin}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v conda &>/dev/null; then
  echo "conda not found. Install Miniconda/Anaconda, then re-run: npm run setup" >&2
  exit 1
fi

if conda env list | awk 'NR>2 {print $1}' | grep -qx "$ENV_NAME"; then
  echo "Updating conda env: $ENV_NAME"
  conda env update -f environment.yml --prune -n "$ENV_NAME"
else
  echo "Creating conda env: $ENV_NAME"
  conda env create -f environment.yml
fi

echo "Installing editable Python services..."
conda run -n "$ENV_NAME" pip install -e "services/cityforesight[dev]" -e "services/urbansense[dev]"

echo ""
echo "Done. Activate and start:"
echo "  conda activate $ENV_NAME"
echo "  npm start"
