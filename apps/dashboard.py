import datetime as dt
from pathlib import Path

import pandas as pd
import streamlit as st

STORE = Path(__file__).resolve().parents[1] / "SmartCFDTradingAgent" / "storage"
DECISIONS_CSV = STORE / "decision_log.csv"
TRADE_LOG = STORE / "trade_log.csv"

st.set_page_config(page_title="SmartCFD Trading Dashboard", layout="wide")
st.title("SmartCFD Trading Dashboard")
st.caption("Friendly view for non-traders – updated by the automated agent")

if DECISIONS_CSV.exists():
    decisions = pd.read_csv(DECISIONS_CSV)
else:
    decisions = pd.DataFrame()

if TRADE_LOG.exists():
    trades = pd.read_csv(TRADE_LOG)
else:
    trades = pd.DataFrame()

col1, col2, col3 = st.columns(3)

if not trades.empty:
    wins = (trades["exit"].notnull() & (trades["exit"] > trades["entry"]) & (trades["side"].str.lower() == "buy")) | (
        trades["exit"].notnull() & (trades["exit"] < trades["entry"]) & (trades["side"].str.lower() == "sell")
    )
    losses = (trades["exit"].notnull()) & (~wins)
    open_positions = trades["exit"].isnull()
    col1.metric("Closed wins", int(wins.sum()))
    col2.metric("Closed losses", int(losses.sum()))
    col3.metric("Open trades", int(open_positions.sum()))
else:
    col1.metric("Closed wins", 0)
    col2.metric("Closed losses", 0)
    col3.metric("Open trades", 0)

st.subheader("Latest Trade Ideas")
if decisions.empty:
    st.info("No decisions logged yet. Once the agent runs you will see new ideas here.")
else:
    latest = decisions.tail(10)[[
        "ts",
        "ticker",
        "side",
        "price",
        "sl",
        "tp",
        "interval",
        "adx",
    ]]
    latest = latest.rename(
        columns={
            "ts": "Timestamp",
            "ticker": "Ticker",
            "side": "Action",
            "price": "Entry Price",
            "sl": "Stop-Loss",
            "tp": "Target",
            "interval": "Timeframe",
            "adx": "Trend strength (ADX)",
        }
    )
    st.table(latest)

st.subheader("Trade Log (paper/live)")
if trades.empty:
    st.info("No trades recorded yet. Live or manual trades will appear here.")
else:
    trades_display = trades.copy()
    trades_display["time"] = pd.to_datetime(trades_display["time"], errors="coerce")
    trades_display = trades_display.sort_values("time", ascending=False).head(20)
    st.dataframe(trades_display)

st.markdown(
    """
### How to use this page
- **Entry Price** is the approximate level suggested by the agent.
- **Stop-Loss / Target** tell you where to exit if things go wrong or right.
- **Trend strength (ADX)** above ~25 usually signals a stronger trend.
- ATR (Average True Range) is already baked into position sizing, so every alert assumes a small, consistent amount of cash at risk.

Need help? Run `scripts\\test_telegram.cmd` to confirm alerts or check the paper account on Alpaca to see the automated orders.
"""
)

last_updated = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
st.caption(f"Last refreshed: {last_updated}")
