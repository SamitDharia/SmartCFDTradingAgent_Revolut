#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
if [[ -z "$VIRTUAL_ENV" && -f "venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi
export CURL_CA_BUNDLE=
export YF_DISABLE_CURL=1
if ! command -v python >/dev/null 2>&1; then
  echo "Error: Python executable not found. Please install Python and ensure it is in your PATH." >&2
  exit 1
fi
python -m SmartCFDTradingAgent.pipeline "$@"
