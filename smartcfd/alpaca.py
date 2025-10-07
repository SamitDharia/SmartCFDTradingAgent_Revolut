import os

def build_api_base(env: str) -> str:
    return "https://paper-api.alpaca.markets" if env.lower() == "paper" else "https://api.alpaca.markets"

def build_headers_from_env() -> dict:
    # Read standard Alpaca env vars; do NOT log or expose values
    print("[DEBUG] Loading Alpaca API keys from environment...")
    key_id = os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_KEY_ID")
    secret = os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY")
    headers = {}
    if key_id and secret:
        print(f"[DEBUG]   - Key ID found: {key_id}")
        print(f"[DEBUG]   - Secret Key found: (length={len(secret)})")
        headers["APCA-API-KEY-ID"] = key_id
        headers["APCA-API-SECRET-KEY"] = secret
    else:
        print("[DEBUG]   - API keys not found in environment variables.")
    return headers
