#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
if [[ -z "$VIRTUAL_ENV" && -f "venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

# Walk-forward (equities per-ticker, daily)
python -m SmartCFDTradingAgent.walk_forward --watch SPY QQQ DIA IWM --interval 1d --years 3 --train-months 6 --test-months 1 --per-ticker

# Walk-forward (crypto per-ticker, hourly)
python -m SmartCFDTradingAgent.walk_forward --watch BTC-USD ETH-USD --interval 1h --years 1 --train-months 3 --test-months 1 --per-ticker

# Daily summary to Telegram
python -m SmartCFDTradingAgent.pipeline --daily-summary --tz Europe/Dublin
