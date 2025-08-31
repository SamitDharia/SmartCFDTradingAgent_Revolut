import sys
from pathlib import Path

import pandas as pd
import numpy as np
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
from SmartCFDTradingAgent.backtester import backtest


def _make_price_df():
    returns = []
    for i in range(20):
        if i % 2 == 1:
            returns.append(0.1 if (i // 2) % 2 == 0 else -0.1)
        else:
            returns.append(0.0)
    price = [100]
    for r in returns:
        price.append(price[-1] * (1 + r))
    price = price[1:]
    idx = pd.date_range('2020-01-01', periods=20)
    close = pd.Series(price, index=idx)
    high = close * 1.01
    low = close * 0.99
    return pd.concat({'AAA': pd.DataFrame({'High': high, 'Low': low, 'Close': close})}, axis=1)


def test_backtester_metrics():
    price_df = _make_price_df()
    pnl, stats, trades = backtest(price_df, {'AAA': 'Buy'}, delay=0,
                                  max_hold=1, cost=0.0,
                                  sl_atr=0.0, tp_atr=0.0, trail_atr=0.0,
                                  risk_pct=0.01, equity=100000)

    daily = pnl['total'].fillna(0)
    if daily.std(ddof=0) == 0:
        expected_sharpe = 0.0
    else:
        expected_sharpe = (daily.mean() / daily.std(ddof=0)) * np.sqrt(len(daily))
    cum = pnl['cum_return']
    peak = cum.cummax()
    dd = (cum - peak) / peak
    expected_dd = float(-dd.min())
    wins = (trades['pnl'] > 0).sum()
    expected_wr = wins / len(trades) if len(trades) else 0.0

    assert stats['sharpe'] == pytest.approx(expected_sharpe)
    assert stats['max_drawdown'] == pytest.approx(expected_dd)
    assert stats['win_rate'] == pytest.approx(expected_wr)
    assert {'entry_time', 'exit_time', 'slippage', 'commission'}.issubset(trades.columns)
