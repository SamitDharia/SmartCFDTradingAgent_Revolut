from __future__ import annotations
import pandas as pd
from SmartCFDTradingAgent.indicators import ema, macd, adx

ADX_THRESHOLD = 15

def generate_signals(
    price_df: pd.DataFrame,
    adx_threshold: int = ADX_THRESHOLD,
    fast_span: int = 12,
    slow_span: int = 26,
    macd_signal: int = 9,
) -> dict[str, str]:
    close = price_df.xs("Close", level=1, axis=1)
    signals: dict[str, str] = {}
    for tkr in close.columns:
        c = close[tkr].dropna()
        if c.size < 50:
            signals[tkr] = "Hold"; continue
        fast, slow = ema(c, fast_span), ema(c, slow_span)
        m = macd(c, fast=fast_span, slow=slow_span, signal=macd_signal)
        a = adx(price_df[tkr]["High"], price_df[tkr]["Low"], price_df[tkr]["Close"]).iloc[-1]
        cond_buy  = (fast.iloc[-1] > slow.iloc[-1]) and (m["hist"].iloc[-1] > 0) and (a >= adx_threshold)
        cond_sell = (fast.iloc[-1] < slow.iloc[-1]) and (m["hist"].iloc[-1] < 0) and (a >= adx_threshold)
        signals[tkr] = "Buy" if cond_buy else ("Sell" if cond_sell else "Hold")
    return signals
