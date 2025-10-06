import sys
import requests
import os

# --- Local Healthcheck Configuration ---
HEALTH_PORT = os.getenv("HEALTH_PORT", "8080")
LOCAL_HEALTH_URL = f"http://localhost:{HEALTH_PORT}/healthz"
LOCAL_TIMEOUT = float(os.getenv("HEALTHCHECK_LOCAL_TIMEOUT_SECONDS", "3"))

# --- Alpaca Fallback Configuration ---
ALPACA_ENV = os.getenv("ALPACA_ENV", "paper")
API_BASE = "https://paper-api.alpaca.markets" if ALPACA_ENV.lower() == "paper" else "https://api.alpaca.markets"
ALPACA_TIMEOUT = float(os.getenv("API_TIMEOUT_SECONDS", "5"))

def build_headers_from_env() -> dict:
    """Reads standard Alpaca env vars to build authentication headers."""
    key_id = os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_KEY_ID")
    secret = os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY")
    headers = {}
    if key_id and secret:
        headers["APCA-API-KEY-ID"] = key_id
        headers["APCA-API-SECRET-KEY"] = secret
    return headers

def main():
    # 1. Try the local /healthz endpoint first
    try:
        r = requests.get(LOCAL_HEALTH_URL, timeout=LOCAL_TIMEOUT)
        if r.status_code == 200:
            print(f"OK: Local healthcheck passed ({LOCAL_HEALTH_URL})")
            sys.exit(0)
        else:
            print(f"WARN: Local healthcheck failed with status {r.status_code}", file=sys.stderr)
    except requests.RequestException as e:
        print(f"WARN: Local healthcheck request failed: {e}", file=sys.stderr)

    # 2. If local check fails, fall back to authenticated Alpaca clock endpoint
    print("INFO: Falling back to authenticated Alpaca healthcheck", file=sys.stderr)
    headers = build_headers_from_env()
    if not headers:
        print("ERROR: Alpaca API keys not found for fallback healthcheck.", file=sys.stderr)
        sys.exit(1)

    try:
        r = requests.get(f"{API_BASE}/v2/clock", timeout=ALPACA_TIMEOUT, headers=headers)
        if r.status_code == 200:
            print("OK: Alpaca fallback healthcheck passed.")
            sys.exit(0)
        else:
            print(f"ERROR: Alpaca fallback healthcheck failed with status {r.status_code}", file=sys.stderr)
            sys.exit(1)
    except requests.RequestException as e:
        print(f"ERROR: Alpaca fallback healthcheck request failed: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
