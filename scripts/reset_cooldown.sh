#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."
rm -f SmartCFDTradingAgent/storage/last_signals.json
echo "Cooldown memory cleared."
