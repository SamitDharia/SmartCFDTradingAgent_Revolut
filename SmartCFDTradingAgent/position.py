from __future__ import annotations


def qty_from_atr(atr_value: float, equity: float, risk_frac: float) -> int:
    """Calculate position size based on ATR and risk parameters.

    Args:
        atr_value: The Average True Range value for the asset.
        equity: Total trading equity available.
        risk_frac: Fraction of equity to risk on the trade.

    Returns:
        The quantity of units to trade, at least 1.
    """

    if atr_value <= 0 or equity <= 0 or risk_frac <= 0:
        return 1
    units = int((equity * risk_frac) / atr_value)
    return max(units, 1)
