from __future__ import annotations

import os

if os.getenv("SKIP_SSL_VERIFY") == "1":
    import SmartCFDTradingAgent.utils.no_ssl  # noqa: F401

import argparse, datetime as dt
from typing import Any

import pandas as pd

from SmartCFDTradingAgent.data_loader import get_price_data
from SmartCFDTradingAgent.signals import generate_signals
from SmartCFDTradingAgent.backtester import backtest
from SmartCFDTradingAgent.utils.logger import get_logger

log = get_logger()

def cli():
    ap = argparse.ArgumentParser(description="Smart CFD Trading Agent – Revolut edition (alerts only)")
    ap.add_argument("--tickers", nargs="+", required=True)
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--interval", default="1d")
    ap.add_argument("--backtest", action="store_true")
    default_risk = float(os.getenv("RISK_PCT", "0.01"))
    ap.add_argument("--risk", type=float, default=default_risk)
    ap.add_argument("--equity", type=float, default=1000.0)
    args = ap.parse_args()

    try:
        price = get_price_data(args.tickers, args.start, args.end, args.interval)
    except Exception as exc:
        log.warning("Data fetch failed for %s: %s", args.tickers, exc)
        return

    if not isinstance(price, pd.DataFrame) or price.empty:
        log.warning("No market data returned for %s between %s and %s.", args.tickers, args.start, args.end)
        return

    sig = generate_signals(price)
    log.info("Signals: %s", sig)

    if args.backtest:
        sig_map = {k: (v.get('action') if isinstance(v, dict) else v) for k, v in sig.items()}
        pnl, stats, _ = backtest(price, sig_map, risk_pct=args.risk, equity=args.equity)
        log.info("Cumulative return: %.2fx | Sharpe %.2f | Max DD %.2f%%", pnl['cum_return'].iloc[-1], stats.get('sharpe', float('nan')), stats.get('max_drawdown', float('nan')) * 100)

if __name__ == "__main__":
    cli()
