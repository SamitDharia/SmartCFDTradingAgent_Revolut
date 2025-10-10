"""
Simple Streamlit dashboard to visualize order lifecycle events.

Run:
  streamlit run scripts/dashboard.py
"""
import os
import time
import pandas as pd
import streamlit as st

EVENTS_CSV = os.getenv("ORDER_EVENTS_CSV", "logs/order_events.csv")

st.set_page_config(page_title="SmartCFD Order Events", layout="wide")
st.title("SmartCFD: Order Lifecycle Events")

if not os.path.exists(EVENTS_CSV):
    st.warning(f"No events file found at {EVENTS_CSV}. Start the bot to generate events.")
    st.stop()

@st.cache_data(ttl=5.0)
def load_events(path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(path)
        if 'ts' in df.columns:
            df['ts'] = pd.to_datetime(df['ts'])
        return df
    except Exception:
        return pd.DataFrame()

df = load_events(EVENTS_CSV)
if df.empty:
    st.info("No events yet.")
    st.stop()

st.subheader("Summary")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Events", len(df))
with col2:
    st.metric("Trade Groups", df['group_gid'].nunique() if 'group_gid' in df.columns else 0)
with col3:
    st.metric("Symbols", df['symbol'].nunique() if 'symbol' in df.columns else 0)

st.subheader("Events by Type")
evt_counts = df['event_type'].value_counts().reset_index()
evt_counts.columns = ['event_type', 'count']
st.dataframe(evt_counts, use_container_width=True)

st.subheader("Recent Events")
st.dataframe(df.sort_values('ts', ascending=False).head(200), use_container_width=True)

st.subheader("Filter")
gid = st.text_input("Filter by group GID")
if gid:
    st.dataframe(df[df['group_gid'] == gid].sort_values('ts'), use_container_width=True)

