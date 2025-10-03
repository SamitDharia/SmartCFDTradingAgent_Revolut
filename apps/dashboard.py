import pandas as pd
import streamlit as st
import altair as alt

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

if not trades.empty and {'entry', 'exit', 'time', 'side'}.issubset(trades.columns):
    trades['time'] = pd.to_datetime(trades['time'], errors='coerce')
    closed = trades.dropna(subset=['exit', 'entry', 'time'])
    def pnl(row):
        entry = float(row['entry'])
        exit_ = float(row['exit'])
        side = str(row['side']).lower()
        return (exit_ - entry) if side != 'sell' else (entry - exit_)
    closed['pnl'] = closed.apply(pnl, axis=1)
    closed = closed.sort_values('time')
    closed['cum_pnl'] = closed['pnl'].cumsum()
    col1.metric("Closed wins", int((closed['pnl'] > 0).sum()))
    col2.metric("Closed losses", int((closed['pnl'] < 0).sum()))
    col3.metric("Open trades", int(trades['exit'].isna().sum()))
else:
    col1.metric("Closed wins", 0)
    col2.metric("Closed losses", 0)
    col3.metric("Open trades", int(trades['exit'].isna().sum() if 'exit' in trades else 0))

st.subheader("Performance Timeline")
if not trades.empty and {'entry', 'exit', 'time', 'side'}.issubset(trades.columns):
    timeline = closed[['time', 'cum_pnl']]
    timeline = timeline.set_index('time')
    st.line_chart(timeline)
else:
    st.info("No closed trades yet. Once trades close you'll see a P&L timeline here.")

st.subheader("Trade Outcomes")
if not trades.empty and {'time', 'side', 'exit', 'entry', 'ticker'}.issubset(trades.columns):
    filter_ticker = st.selectbox("Filter by ticker", options=['All'] + sorted(trades['ticker'].dropna().unique().tolist()))
    view = trades.copy()
    if filter_ticker != 'All':
        view = view[view['ticker'] == filter_ticker]
    view['time'] = pd.to_datetime(view['time'], errors='coerce')
    st.dataframe(view.sort_values('time', ascending=False).head(50))
else:
    st.info("No trades recorded yet.")

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
    st.dataframe(latest)

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
