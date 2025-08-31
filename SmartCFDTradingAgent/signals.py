from __future__ import annotations

import pandas as pd

from SmartCFDTradingAgent.indicators import ema, macd, adx

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - only for type hints
    from SmartCFDTradingAgent.ml_models import PriceDirectionModel

ADX_THRESHOLD = 15

def generate_signals(
    price_df: pd.DataFrame,
    adx_threshold: int = ADX_THRESHOLD,
    fast_span: int = 12,
    slow_span: int = 26,
    macd_signal: int = 9,
    ml_model: "PriceDirectionModel | None" = None,
    ml_threshold: float = 0.6,
) -> dict[str, str]:
    close = price_df.xs("Close", level=1, axis=1)
    signals: dict[str, str] = {}
    for tkr in close.columns:
        c = close[tkr].dropna()
        if c.size < 50:
            signals[tkr] = "Hold"
            continue

        fast, slow = ema(c, fast_span), ema(c, slow_span)
        m = macd(c, fast=fast_span, slow=slow_span, signal=macd_signal)
        a = adx(price_df[tkr]["High"], price_df[tkr]["Low"], price_df[tkr]["Close"]).iloc[-1]
        cond_buy = (fast.iloc[-1] > slow.iloc[-1]) and (m["hist"].iloc[-1] > 0) and (a >= adx_threshold)
        cond_sell = (fast.iloc[-1] < slow.iloc[-1]) and (m["hist"].iloc[-1] < 0) and (a >= adx_threshold)
        side = "Buy" if cond_buy else ("Sell" if cond_sell else "Hold")

        # Optionally blend with ML model prediction
        if ml_model is not None:
            try:
                ml_side, prob = ml_model.predict_signal(c)
                if prob >= ml_threshold:
                    if side == "Hold":
                        side = ml_side
                    elif ml_side != side:
                        side = "Hold"
            except Exception:
                # On any ML error, fall back to indicator signal
                pass

        signals[tkr] = side
    return signals
