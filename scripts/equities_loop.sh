#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
# shellcheck disable=SC1091
source venv/bin/activate
export CURL_CA_BUNDLE=
export YF_DISABLE_CURL=1
python -m SmartCFDTradingAgent.pipeline --config configs/equities.yml --profile equities_daily "$@"
