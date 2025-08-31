from __future__ import annotations

import pandas as pd

from SmartCFDTradingAgent.indicators import ema, rsi, adx

ADX_THRESHOLD = 20


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def generate_signals(
    price_df: pd.DataFrame,
    adx_threshold: int = ADX_THRESHOLD,
    ema_fast: int = 20,
    ema_slow: int = 50,
    rsi_period: int = 14,
    rsi_buy: float = 55.0,
    rsi_sell: float = 45.0,
    **_: object,
) -> dict[str, dict]:
    """Generate simple trend-following signals.

    Returns a mapping of ticker -> {"action": str, "confidence": float}.
    Confidence is a loose 0-1 score based on how strongly the conditions are met.
    """
    close = price_df.xs("Close", level=1, axis=1)
    out: dict[str, dict] = {}
    for tkr in close.columns:
        c = close[tkr].dropna()
        if c.size < max(ema_slow, rsi_period) + 1:
            out[tkr] = {"action": "Hold", "confidence": 0.0}
            continue

        f = ema(c, ema_fast)
        s = ema(c, ema_slow)
        r = rsi(c, rsi_period)
        a = adx(price_df[tkr]["High"], price_df[tkr]["Low"], price_df[tkr]["Close"]).iloc[-1]

        action = "Hold"
        confidence = 0.0

        if f.iloc[-1] > s.iloc[-1] and r.iloc[-1] > rsi_buy and a > adx_threshold:
            action = "Buy"
            confidence = _clamp(min(
                (f.iloc[-1] - s.iloc[-1]) / abs(s.iloc[-1]),
                (r.iloc[-1] - rsi_buy) / 45.0,
                (a - adx_threshold) / float(adx_threshold),
            ))
        elif f.iloc[-1] < s.iloc[-1] and r.iloc[-1] < rsi_sell and a > adx_threshold:
            action = "Sell"
            confidence = _clamp(min(
                (s.iloc[-1] - f.iloc[-1]) / abs(s.iloc[-1]),
                (rsi_sell - r.iloc[-1]) / 45.0,
                (a - adx_threshold) / float(adx_threshold),
            ))

        out[tkr] = {"action": action, "confidence": float(confidence)}
    return out
