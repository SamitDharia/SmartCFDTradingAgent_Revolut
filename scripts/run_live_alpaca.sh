#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
if [[ -z "${VIRTUAL_ENV:-}" && -f "venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi
python -m SmartCFDTradingAgent.pipeline --config configs/equities.yml --profile equities_daily --broker alpaca "$@"
