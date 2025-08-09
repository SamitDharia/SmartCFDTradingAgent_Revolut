#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
D=$(date +%Y%m%d)
LOG="SmartCFDTradingAgent/logs/${D}.log"
${EDITOR:-less} "$LOG"
