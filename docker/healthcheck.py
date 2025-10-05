import sys
import requests
import os

ALPACA_ENV = os.getenv("ALPACA_ENV", "paper")
API_BASE = "https://paper-api.alpaca.markets" if ALPACA_ENV.lower() == "paper" else "https://api.alpaca.markets"
TIMEOUT = float(os.getenv("API_TIMEOUT_SECONDS", "5"))

try:
    r = requests.get(f"{API_BASE}/v2/clock", timeout=TIMEOUT)
    sys.exit(0 if r.status_code == 200 else 1)
except Exception:
    sys.exit(1)
