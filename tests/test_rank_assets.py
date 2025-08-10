import sys
from pathlib import Path

import pandas as pd

# Ensure project root on path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from SmartCFDTradingAgent import rank_assets


def test_top_n_composite_ranking(monkeypatch):
    tickers = ["AAA", "BBB", "CCC"]
    idx = pd.date_range("2020-01-01", periods=10, freq="D")
    arrays = pd.MultiIndex.from_product([tickers, ["Close", "Volume"]])
    df = pd.DataFrame(index=idx, columns=arrays)

    # AAA: strong momentum, high volume, low volatility
    df["AAA", "Close"] = [10, 11, 12, 13, 14, 15, 16, 17, 18, 19]
    df["AAA", "Volume"] = [100] * 10

    # BBB: negative momentum, medium volume, high volatility
    df["BBB", "Close"] = [10, 8, 12, 9, 13, 8, 14, 7, 15, 6]
    df["BBB", "Volume"] = [50] * 10

    # CCC: flat, low volume, very low volatility
    df["CCC", "Close"] = [10] * 10
    df["CCC", "Volume"] = [10] * 10

    def fake_get_price_data(tickers, start, end, interval="1d"):
        return df

    monkeypatch.setattr(rank_assets, "get_price_data", fake_get_price_data)

    lookbacks = {"sharpe": 5, "momentum": 5, "volume": 5, "volatility": 5}
    weights = {"sharpe": 0.0, "momentum": 0.5, "volume": 0.3, "volatility": -0.2}

    ranked = rank_assets.top_n(tickers, 3, lookbacks=lookbacks, weights=weights)
    assert ranked == ["AAA", "CCC", "BBB"]

