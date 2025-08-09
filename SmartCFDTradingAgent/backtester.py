from __future__ import annotations
from typing import Dict
import pandas as pd, numpy as np
from SmartCFDTradingAgent.indicators import atr

def _sig_to_pos(sig: str) -> int:
    return {"Buy": 1, "Sell": -1}.get(sig, 0)

def backtest(price_df: pd.DataFrame, signal_map: Dict[str, str],
             delay: int = 1, max_hold: int = 20, cost: float = 0.0002,
             sl: float = 0.02, tp: float = 0.04, risk_pct: float = 0.01,
             equity: float = 100_000) -> pd.DataFrame:
    close = price_df.xs("Close", level=1, axis=1).copy()
    rets  = close.pct_change().shift(-delay).fillna(0.0)

    atrs = {}
    for tkr in signal_map:
        high = price_df[tkr]["High"]
        low  = price_df[tkr]["Low"]
        c    = price_df[tkr]["Close"]
        val = atr(high, low, c).iloc[-1]
        if pd.isna(val):
            raise RuntimeError(f"ATR is NaN for {tkr}")
        atrs[tkr] = float(val)

    pnl = pd.DataFrame(index=rets.index, columns=signal_map.keys(), dtype=float).fillna(0.0)

    for tkr, entry_sig in signal_map.items():
        pos = 0
        hold = 0
        entry_price = None
        qty = 0

        for i, date in enumerate(rets.index):
            price_now = close.at[date, tkr]
            if price_now == 0 or np.isnan(price_now):
                continue

            if pos == 0 and _sig_to_pos(entry_sig) != 0 and i >= delay:
                pos = _sig_to_pos(entry_sig)
                qty = max(int((equity * risk_pct) / max(atrs[tkr], 1e-8)), 1)
                entry_price = price_now
                hold = 0
                pnl.at[date, tkr] -= cost
                continue

            if pos != 0:
                hold += 1
                pnl.at[date, tkr] += pos * qty * rets.at[date, tkr]
                hit_sl = (pos == 1 and price_now <= entry_price * (1 - sl)) or (pos == -1 and price_now >= entry_price * (1 + sl))
                hit_tp = (pos == 1 and price_now >= entry_price * (1 + tp)) or (pos == -1 and price_now <= entry_price * (1 - tp))
                if hit_sl or hit_tp:
                    pos = 0
                    entry_price = None
                    pnl.at[date, tkr] -= cost
                    continue
                if hold >= max_hold:
                    pos = 0
                    entry_price = None
                    pnl.at[date, tkr] -= cost

    pnl["total"] = pnl.sum(axis=1, skipna=True)
    pnl["cum_return"] = (1 + pnl["total"].fillna(0)).cumprod()
    return pnl
