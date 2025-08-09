#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
LATEST=$(ls -t SmartCFDTradingAgent/logs/*.log 2>/dev/null | head -n 1)
if [[ -z "$LATEST" ]]; then
  echo "No log files found."
else
  ${EDITOR:-less} "$LATEST"
fi
