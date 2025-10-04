#!/usr/bin/env python3
"""Quick Alpaca credentials + crypto health check.

Usage:
  python scripts/check_alpaca.py

Loads .env, verifies REST connectivity, warns about common misconfigurations
and tries a small crypto data request to validate permissions.
"""
from __future__ import annotations

import os
import sys
import datetime as dt

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()

    key = os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY")
    sec = os.getenv("APCA_API_SECRET_KEY") or os.getenv("ALPACA_API_SECRET")
    base = os.getenv("APCA_API_BASE_URL") or os.getenv("ALPACA_API_BASE_URL") or "https://paper-api.alpaca.markets"

    print("Alpaca base:", base)
    if base.rstrip("/").endswith("/v2"):
        print("WARNING: Remove trailing '/v2' from APCA_API_BASE_URL. Use:")
        print("         https://paper-api.alpaca.markets (paper) or https://api.alpaca.markets (live)")

    if not key or not sec:
        print("ERROR: Missing APCA_API_KEY_ID/APCA_API_SECRET_KEY in environment")
        return 2

    try:
        import alpaca_trade_api as tradeapi
    except Exception as exc:
        print("ERROR: alpaca-trade-api not installed:", exc)
        return 3

    try:
        api = tradeapi.REST(key, sec, base, api_version="v2")
    except Exception as exc:
        print("ERROR: Failed to construct REST client:", exc)
        return 4

    # Account status
    try:
        acct = api.get_account()
        print("Account status:", getattr(acct, "status", "?"))
        print("Equity:", getattr(acct, "equity", "?"))
        print("Buying power:", getattr(acct, "buying_power", "?"))
        print("Trading blocked:", getattr(acct, "trading_blocked", "?"))
    except Exception as exc:
        print("ERROR: Account retrieval failed:", exc)
        return 5

    # Crypto asset visibility
    try:
        assets = api.get_assets(status="active", asset_class="crypto")
        syms = [getattr(a, "symbol", "?") for a in assets][:10]
        print("Active crypto assets (sample):", ", ".join(syms) or "none")
    except Exception as exc:
        print("WARN: Could not list crypto assets:", exc)

    # Crypto bars sanity
    try:
        end = dt.datetime.utcnow()
        start = end - dt.timedelta(days=2)
        # Use slash-form symbols for Alpaca
        bars = api.get_crypto_bars(["BTC/USD", "ETH/USD"], tradeapi.TimeFrame.Hour, start.isoformat(), end.isoformat(), limit=100)
        df = getattr(bars, "df", None)
        if df is not None and not df.empty:
            print("Crypto bars OK:", df.index.get_level_values(0).unique().tolist()[:2])
        else:
            print("WARN: No crypto bars returned for BTC/USD, ETH/USD in last 48h")
    except Exception as exc:
        print("ERROR: Crypto bars request failed:", exc)
        print("       Ensure crypto is enabled for your account and base URL matches your keys.")
        return 6

    print("Alpaca check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

