#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

LOGFILE="market_loop.log"
exec > >(tee -a "$LOGFILE") 2>&1

if [[ -z "$VIRTUAL_ENV" && -f "venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

scripts/run_bot.sh --watch SPY QQQ DIA IWM --size 4 --interval 1d --adx 15 \
  --max-trades 2 --grace 120 --risk 0.01 --equity 1000 "$@"

