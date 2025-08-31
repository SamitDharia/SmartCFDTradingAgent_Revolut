from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from SmartCFDTradingAgent.calculator import atr


def _sig_to_pos(sig: str) -> int:
    """Convert signal string to numeric position."""
    return {"Buy": 1, "Sell": -1}.get(sig, 0)


def backtest(price_df: pd.DataFrame, signal_map: Dict[str, str],
             delay: int = 1, max_hold: int = 20, cost: float = 0.0002,
             sl_atr: float = 2.0, tp_atr: float = 4.0, trail_atr: float = 0.0,
             risk_pct: float = 0.01, equity: float = 100_000
             ) -> Tuple[pd.DataFrame, Dict[str, float], pd.DataFrame]:
    close = price_df.xs("Close", level=1, axis=1).copy()
    high_df = price_df.xs("High", level=1, axis=1)
    low_df = price_df.xs("Low", level=1, axis=1)
    rets  = close.pct_change().shift(-delay).fillna(0.0)

    atrs: Dict[str, float] = {}
    for tkr in signal_map:
        high = price_df[tkr]["High"]
        low = price_df[tkr]["Low"]
        c = price_df[tkr]["Close"]
        val = atr(high, low, c).iloc[-1]
        if pd.isna(val):
            raise RuntimeError(f"ATR is NaN for {tkr}")
        atrs[tkr] = float(val)

    pnl = pd.DataFrame(index=rets.index, columns=signal_map.keys(), dtype=float).fillna(0.0)

    trades: List[dict] = []

    for tkr, entry_sig in signal_map.items():
        pos = 0
        hold = 0
        entry_price: float | None = None
        entry_date = None
        qty = 0
        entry_slip = 0.0
        stop = take = trail = None
        atr_val = atrs[tkr]

        for i, date in enumerate(rets.index):
            price_now = close.at[date, tkr]
            bar_high = high_df.at[date, tkr]
            bar_low = low_df.at[date, tkr]
            if price_now == 0 or np.isnan(price_now):
                continue

            if pos == 0 and _sig_to_pos(entry_sig) != 0 and i >= delay:
                pos = _sig_to_pos(entry_sig)
                risk_budget = equity * risk_pct
                k = 1.0
                qty = max(int(risk_budget / max(k * atrs[tkr], 1e-8)), 1)
                qty = max(int((equity * risk_pct) / max(atr_val, 1e-8)), 1)

                entry_price = price_now
                entry_date = date
                hold = 0
                signal_price = close.iloc[i - delay][tkr] if i >= delay else price_now
                entry_slip = abs(entry_price - signal_price)
                pnl.at[date, tkr] -= cost
                stop = take = trail = None
                if sl_atr > 0:
                    stop = entry_price - pos * sl_atr * atr_val
                if tp_atr > 0:
                    take = entry_price + pos * tp_atr * atr_val
                if trail_atr > 0:
                    trail = entry_price - pos * trail_atr * atr_val
                continue

            if pos != 0:
                hold += 1
                pnl.at[date, tkr] += pos * qty * rets.at[date, tkr]

                if trail is not None and trail_atr > 0:
                    if pos == 1:
                        trail = max(trail, bar_high - trail_atr * atr_val)
                    else:
                        trail = min(trail, bar_low + trail_atr * atr_val)

                hit_sl = False
                hit_tp = False
                hit_trail = False
                if stop is not None:
                    if pos == 1:
                        hit_sl = bar_low <= stop
                    else:
                        hit_sl = bar_high >= stop
                if take is not None:
                    if pos == 1:
                        hit_tp = bar_high >= take
                    else:
                        hit_tp = bar_low <= take
                if trail is not None:
                    if pos == 1:
                        hit_trail = bar_low <= trail
                    else:
                        hit_trail = bar_high >= trail

                exit_price = None
                if hit_sl:
                    exit_price = stop
                elif hit_tp:
                    exit_price = take
                elif hit_trail:
                    exit_price = trail
                elif hold >= max_hold:
                    exit_price = price_now

                if exit_price is not None:
                    exit_date = date
                    exit_slip = abs(exit_price - close.iloc[i - 1][tkr]) if i > 0 else 0.0
                    pnl.at[date, tkr] -= cost
                    trade_pnl = pos * qty * ((exit_price - entry_price) / entry_price)
                    trades.append(
                        {
                            "ticker": tkr,
                            "entry_time": entry_date,
                            "exit_time": exit_date,
                            "entry_price": entry_price,
                            "exit_price": exit_price,
                            "pnl": trade_pnl - (2 * cost),
                            "slippage": entry_slip + exit_slip,
                            "commission": 2 * cost,
                        }
                    )
                    pos = 0
                    entry_price = None
                    entry_date = None
                    entry_slip = 0.0
                    stop = take = trail = None

    pnl["total"] = pnl.sum(axis=1, skipna=True)
    pnl["cum_return"] = (1 + pnl["total"].fillna(0)).cumprod() - 1

    daily = pnl["total"].fillna(0)
    if daily.std(ddof=0) == 0:
        sharpe = 0.0
    else:
        sharpe = (daily.mean() / daily.std(ddof=0)) * np.sqrt(len(daily))

    cum = pnl["cum_return"]
    peak = cum.cummax()
    dd = (cum - peak) / peak
    max_dd = float(-dd.min()) if len(dd) else 0.0
    wins = sum(1 for t in trades if t.get("pnl", 0) > 0)
    win_rate = wins / len(trades) if trades else 0.0

    stats = {
        "sharpe": float(sharpe),
        "max_drawdown": max_dd,
        "win_rate": float(win_rate),
    }

    trades_df = pd.DataFrame(trades)
    return pnl, stats, trades_df

