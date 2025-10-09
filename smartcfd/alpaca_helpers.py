import os

def build_api_base(env: str) -> str:
    return "https://paper-api.alpaca.markets" if env.lower() == "paper" else "https://api.alpaca.markets"

def build_headers_from_env() -> dict:
    # Read standard Alpaca env vars; do NOT log or expose values
    key_id = os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_KEY_ID")
    secret = os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY")
    headers = {}
    if key_id and secret:
        headers["APCA-API-KEY-ID"] = key_id
        headers["APCA-API-SECRET-KEY"] = secret
    return headers
