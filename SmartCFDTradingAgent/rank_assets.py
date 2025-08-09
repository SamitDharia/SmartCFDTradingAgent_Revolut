from __future__ import annotations
import SmartCFDTradingAgent.utils.no_ssl  # must be first
import datetime as dt
import pandas as pd
from SmartCFDTradingAgent.data_loader import get_price_data

def _sharpe_30d(close: pd.Series) -> float:
    r = close.pct_change().dropna()
    if len(r) < 2: return 0.0
    mean = r.mean(); std = r.std() or 1e-9
    return (mean / std) * (252**0.5)

def top_n(tickers, n: int):
    tickers = list(dict.fromkeys(tickers))
    end = dt.date.today().isoformat()
    start = (dt.date.today() - dt.timedelta(days=60)).isoformat()
    try:
        df = get_price_data(tickers, start, end, interval="1d")
        scores = {}
        for t in tickers:
            try:
                close = df[t]["Close"].dropna()
                scores[t] = _sharpe_30d(close.tail(30))
            except Exception:
                scores[t] = -1e9
        ranked = sorted(tickers, key=lambda t: scores.get(t, -1e9), reverse=True)
        return ranked[:min(n, len(ranked))]
    except Exception as e:
        print(f"[rank_assets] daily ranking failed ({e}); returning unranked first {n}.")
        return tickers[:min(n, len(tickers))]
