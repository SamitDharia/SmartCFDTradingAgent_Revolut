from datetime import datetime
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

STORE = Path(__file__).resolve().parents[1] / "SmartCFDTradingAgent" / "storage"
DECISIONS_CSV = STORE / "decision_log.csv"
TRADE_LOG = STORE / "trade_log.csv"

st.set_page_config(page_title="SmartCFD Trading Dashboard", layout="wide")

st.markdown(
    """
    <style>
    .main {background-color:#f1f5f9;}
    .metric-card {
        background:#ffffff;
        padding:18px 22px;
        border-radius:16px;
        box-shadow:0 12px 24px rgba(15,23,42,0.08);
        border:1px solid rgba(148,163,184,0.2);
    }
    .metric-card h3 {margin:0;font-size:16px;color:#475569;}
    .metric-card p {margin-top:10px;font-size:26px;font-weight:700;color:#0f172a;}
    .section-card {
        background:#ffffff;
        padding:24px;
        border-radius:18px;
        box-shadow:0 18px 32px rgba(15,23,42,0.08);
        border:1px solid rgba(226,232,240,0.7);
    }
    .stDataFrame {border-radius:12px;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("SmartCFD Trading Dashboard")
st.caption("Friendly view for non-traders – refreshed automatically by the agent")

# ------------------------------------------------------------------ data load
def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, on_bad_lines="skip", engine="python")


decisions = _safe_read_csv(DECISIONS_CSV)
trades = _safe_read_csv(TRADE_LOG)

# ---------------------------------------------------------------- metrics
metric_cols = st.columns(3)
if not trades.empty and {"entry", "exit", "time", "side"}.issubset(trades.columns):
    trades["time"] = pd.to_datetime(trades["time"], errors="coerce")
    closed = trades.dropna(subset=["entry", "exit", "time"]).copy()
    if not closed.empty:
        closed["entry"] = closed["entry"].astype(float)
        closed["exit"] = closed["exit"].astype(float)

        def _pnl(row):
            side = str(row["side"]).lower()
            return row["exit"] - row["entry"] if side != "sell" else row["entry"] - row["exit"]

        closed["pnl"] = closed.apply(_pnl, axis=1)
        closed = closed.sort_values("time")
        closed["cum_pnl"] = closed["pnl"].cumsum()
    else:
        closed = pd.DataFrame()
else:
    closed = pd.DataFrame()

wins = int((closed["pnl"] > 0).sum()) if not closed.empty else 0
losses = int((closed["pnl"] < 0).sum()) if not closed.empty else 0
open_trades = int(trades["exit"].isna().sum()) if not trades.empty and "exit" in trades else 0

for col, label, value in zip(
    metric_cols,
    ["Closed wins", "Closed losses", "Open trades"],
    [wins, losses, open_trades],
):
    col.markdown(
        f"<div class='metric-card'><h3>{label}</h3><p>{value}</p></div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------- tabs
perf_tab, signals_tab = st.tabs(["📈 Performance", "💡 Signals"])

with perf_tab:
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.subheader("Cumulative P&L")
    if not closed.empty:
        pnl_chart = (
            alt.Chart(closed)
            .mark_area(color="#60a5fa", opacity=0.6)
            .encode(
                x=alt.X("time:T", title="Time"),
                y=alt.Y("cum_pnl:Q", title="Cumulative P&L"),
                tooltip=["time:T", "pnl:Q", "cum_pnl:Q", "ticker:N"],
            )
            .properties(height=280)
        )
        st.altair_chart(pnl_chart, use_container_width=True)
    else:
        st.info("No closed trades yet. Once trades close you'll see a P&L timeline here.")

    st.subheader("Trade history")
    if not trades.empty and "time" in trades.columns:
        filtered = trades.copy()
        filtered["time"] = pd.to_datetime(filtered["time"], errors="coerce")
        filtered = filtered.sort_values("time", ascending=False)
        st.dataframe(filtered.head(100))
    else:
        st.info("No trades recorded yet.")
    st.markdown("</div>", unsafe_allow_html=True)

with signals_tab:
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    st.subheader("Signal overview")
    if decisions.empty:
        st.info("No decisions logged yet. The agent will populate this section once trades are evaluated.")
    else:
        decisions["timestamp"] = pd.to_datetime(decisions["ts"], errors="coerce")
        summary = decisions.groupby("side").size().reset_index(name="count")
        signal_chart = (
            alt.Chart(summary)
            .mark_bar(color="#a855f7")
            .encode(x=alt.X("side:N", title="Signal"), y=alt.Y("count:Q", title="Count"), tooltip=["side", "count"])
            .properties(height=260)
        )
        st.altair_chart(signal_chart, use_container_width=True)

        st.subheader("Latest trade ideas")
        show_cols = ["ts", "ticker", "side", "price", "sl", "tp", "interval", "adx"]
        display = decisions.tail(50)[show_cols].rename(
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
        st.dataframe(display)
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown(
    """
<div style="background:#eef2ff;border-radius:14px;padding:16px 20px;margin-top:28px;color:#312e81;">
  <strong>Need help?</strong> Run <code>scripts\test_telegram.cmd</code> to confirm alerts or check the Alpaca paper account to review automated orders.
</div>
""",
    unsafe_allow_html=True,
)

last_updated = datetime.now().strftime("%Y-%m-%d %H:%M")
st.caption(f"Last refreshed: {last_updated}")
