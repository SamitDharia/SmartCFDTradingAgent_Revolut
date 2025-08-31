from __future__ import annotations

import os

if os.getenv("SKIP_SSL_VERIFY") == "1":
    import SmartCFDTradingAgent.utils.no_ssl  # noqa: F401

import argparse, datetime as dt
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
    ap.add_argument("--risk", type=float, default=0.01)
    ap.add_argument("--equity", type=float, default=1000.0)
    args = ap.parse_args()

    price = get_price_data(args.tickers, args.start, args.end, args.interval)
    sig = generate_signals(price)
    log.info("Signals: %s", sig)

    if args.backtest:
        pnl = backtest(price, sig, risk_pct=args.risk, equity=args.equity)
        log.info("Cumulative return: %.2fx", pnl["cum_return"].iloc[-1])

if __name__ == "__main__":
    cli()
