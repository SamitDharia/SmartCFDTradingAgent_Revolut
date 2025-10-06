#!/bin/bash
set -Eeuo pipefail

echo "[entrypoint] Starting SmartCFDTradingAgent (cloud-first minimal run)"
echo "[entrypoint] Timezone: ${TIMEZONE:-Europe/Dublin}"
echo "[entrypoint] Mode: ${ALPACA_ENV:-paper}"
echo "[entrypoint] Reconnect reconcile: ${ON_RECONNECT_RECONCILE:-true}"

# Simple preflight: show Python and installed versions for debugging
python --version || true
pip list --format=columns | head -n 50 || true

# Optional: run the CI smoke test so we know container wiring is OK
if [ "${RUN_CONTAINER_SMOKE_TEST:-1}" = "1" ]; then
  echo "[entrypoint] Running container smoke test (pytest -q tests/test_smoke.py)"
  pytest -q tests/test_smoke.py --maxfail=1 --disable-warnings || echo "[entrypoint] Smoke test failed or not present; continuing."
fi

# Start minimal runtime loop (connectivity + future agent hook)
echo "[entrypoint] Launching runner..."
exec python /app/docker/runner.py
