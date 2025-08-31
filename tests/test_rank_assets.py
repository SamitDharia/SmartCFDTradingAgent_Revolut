import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure project root on path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from SmartCFDTradingAgent import rank_assets


def test_ranking_and_liquidity_filter(monkeypatch):
    tickers = ["AAA", "BBB", "CCC"]
    idx = pd.date_range("2020-01-01", periods=61, freq="D")
    arrays = pd.MultiIndex.from_product([tickers, ["Close", "Volume"]])
    df = pd.DataFrame(index=idx, columns=arrays, dtype=float)

    # AAA: strong constant returns, high volume
    df["AAA", "Close"] = 100 * (1.05) ** np.arange(len(idx))
    df["AAA", "Volume"] = 1000

    # BBB: modest constant returns, high volume
    df["BBB", "Close"] = 100 * (1.02) ** np.arange(len(idx))
    df["BBB", "Volume"] = 1000

    # CCC: positive returns but extremely low volume (to be excluded)
    df["CCC", "Close"] = 100 * (1.01) ** np.arange(len(idx))
    df["CCC", "Volume"] = 1

    def fake_get_price_data(tickers, start, end, interval="1d"):
        return df

    monkeypatch.setattr(rank_assets, "get_price_data", fake_get_price_data)

    ranked = rank_assets.top_n(
        tickers,
        3,
        lookback=60,
        min_dollar_volume=100_000,
    )

    assert ranked == ["AAA", "BBB"]

