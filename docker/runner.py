import os
import time
import json
from datetime import datetime, timezone
import requests

TIMEZONE = os.getenv("TIMEZONE", "Europe/Dublin")
ALPACA_ENV = os.getenv("ALPACA_ENV", "paper")
API_BASE = "https://paper-api.alpaca.markets" if ALPACA_ENV.lower() == "paper" else "https://api.alpaca.markets"
API_TIMEOUT = float(os.getenv("API_TIMEOUT_SECONDS", "10"))
BACKOFF_MAX = int(os.getenv("NETWORK_MAX_BACKOFF_SECONDS", "60"))

def log(event: str, **kw):
    payload = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **kw}
    print(json.dumps(payload), flush=True)

def check_connectivity():
    try:
        r = requests.get(f"{API_BASE}/v2/clock", timeout=API_TIMEOUT)
        ok = r.status_code == 200
        return ok, r.status_code
    except Exception as e:
        return False, str(e)

def main():
    log("runner.start", tz=TIMEZONE, env=ALPACA_ENV, base=API_BASE)

    backoff = 2
    while True:
        ok, info = check_connectivity()
        if ok:
            log("runner.health.ok", detail=info)
            backoff = 2
        else:
            log("runner.health.fail", detail=info)
            backoff = min(backoff * 2, BACKOFF_MAX)
        # Placeholder for real agent loop (next PR)
        log("runner.heartbeat", sleep_seconds=backoff)
        time.sleep(backoff)

if __name__ == "__main__":
    main()
