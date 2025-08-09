from __future__ import annotations
def qty_from_atr(price: float, atr_value: float, equity: float, risk_frac: float) -> int:
    if atr_value <= 0 or equity <= 0 or risk_frac <= 0:
        return 1
    units = int((equity * risk_frac) / atr_value)
    return max(units, 1)
