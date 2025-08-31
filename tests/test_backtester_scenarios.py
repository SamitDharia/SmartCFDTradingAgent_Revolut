import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from SmartCFDTradingAgent.backtester import backtest


def _build_price():
    idx = pd.date_range("2020-01-01", periods=20)

    def _df(prices):
        close = pd.Series(prices, index=idx)
        high = close * 1.01
        low = close * 0.99
        return pd.DataFrame({"High": high, "Low": low, "Close": close})

    aaa = [100, 90] + [90] * 18        # Long -> stop loss
    bbb = [100, 90] + [90] * 18        # Short -> take profit
    ccc = [100, 102, 103] + [103] * 17  # Time stop

    price = pd.concat({"AAA": _df(aaa), "BBB": _df(bbb), "CCC": _df(ccc)}, axis=1)
    return price


def test_long_short_time_stop_non_nan_equity():
    price_df = _build_price()
    signals = {"AAA": "Buy", "BBB": "Sell", "CCC": "Buy"}
    pnl, stats, trades = backtest(
        price_df,
        signals,
        delay=0,
        max_hold=2,
        cost=0.0,
        sl_atr=2.5,
        tp_atr=2.5,
        risk_pct=0.1,
        equity=10_000,
    )

    assert not pnl["cum_return"].isna().any()
    t = trades.groupby("ticker").first()
    assert set(t.index) == {"AAA", "BBB", "CCC"}
    assert t.loc["AAA", "pnl"] < 0  # stopped out
    assert t.loc["BBB", "pnl"] > 0  # take profit
    assert t.loc["CCC", "exit_time"] == price_df.index[2]  # time stop
