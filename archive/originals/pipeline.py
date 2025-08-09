from __future__ import annotations
import argparse, time, datetime as dt
from dotenv import load_dotenv
load_dotenv()

from datetime import timezone
from SmartCFDTradingAgent.utils.logger import get_logger
from SmartCFDTradingAgent.utils.market_time import market_open
from SmartCFDTradingAgent.utils.telegram import send as tg_send
from SmartCFDTradingAgent.rank_assets import top_n
from SmartCFDTradingAgent.data_loader import get_price_data
from SmartCFDTradingAgent.signals import generate_signals
from SmartCFDTradingAgent.backtester import backtest

log = get_logger()

def safe_send(msg: str) -> None:
    try:
        tg_send(msg)
    except Exception as e:
        log.error("Telegram send failed: %s", e)

def run_cycle(watch, size, grace, risk, equity, force=False, interval="1d", adx=15):
    if not force and not market_open():
        log.info("Market closed – skipping cycle."); return

    tickers = top_n(watch, size)
    end = dt.date.today().isoformat()
    start = (dt.date.today() - dt.timedelta(days=365)).isoformat()
    price = get_price_data(tickers, start, end, interval=interval)
    sig   = generate_signals(price, adx_threshold=adx)
    log.info("Signals: %s", sig)

    lines = [f"PRE-TRADE {dt.datetime.now(timezone.utc):%Y-%m-%d %H:%MZ} (int={interval}, ADX>={adx})"]
    for tkr, side in sig.items():
        if side == "Hold":
            continue
        last = price[tkr]["Close"].iloc[-1]
        sl   = round(last * (0.98 if side == "Buy" else 1.02), 2)
        tp   = round(last * (1.04 if side == "Buy" else 0.96), 2)
        emoji = "🟢" if side == "Buy" else "🔴"
        lines.append(f"{emoji} {tkr:<8} {side:>4} | Px {last:.2f} | SL {sl:.2f} | TP {tp:.2f}")
    txt = "\n".join(lines) if len(lines) > 1 else "No trades today."
    safe_send(txt); log.info("%s", txt.replace("\n", " | "))

    time.sleep(grace)

    pnl = backtest(price, sig, max_hold=5, cost=0.0002, sl=0.02, tp=0.04, risk_pct=risk, equity=equity)
    last_cum = pnl["cum_return"].iloc[-1]
    safe_send(f"Backtest cum return (1yr): {last_cum:.2f}x")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", nargs="+", required=True)
    ap.add_argument("--size", type=int, default=5)
    ap.add_argument("--grace", type=int, default=900)
    ap.add_argument("--risk", type=float, default=0.01)
    ap.add_argument("--equity", type=float, default=1000.0)
    ap.add_argument("--force", action="store_true", help="Run even if market is closed")
    ap.add_argument("--interval", default="1d", help="yfinance interval (e.g. 1d, 1h, 30m)")
    ap.add_argument("--adx", type=int, default=15, help="ADX threshold for signals")
    args = ap.parse_args()
    try:
        run_cycle(args.watch, args.size, args.grace, args.risk, args.equity, args.force, args.interval, args.adx)
    except Exception as e:
        log.exception("Pipeline crashed: %s", e)
        safe_send(f"⚠️ SmartCFD crashed\n{e}")

if __name__ == "__main__":
    main()
