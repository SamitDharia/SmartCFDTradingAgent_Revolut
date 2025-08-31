import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))
from SmartCFDTradingAgent.backtester import backtest
from SmartCFDTradingAgent.indicators import atr


def _base_df():
    idx = pd.date_range('2020-01-01', periods=20)
    close = pd.Series(100.0, index=idx)
    high = close + 0.5
    low = close - 0.5
    return pd.concat({'AAA': pd.DataFrame({'High': high, 'Low': low, 'Close': close})}, axis=1)


def test_stop_loss_hit_intrabar():
    df = _base_df()
    df.loc[df.index[18], ('AAA', 'Low')] = 98.0
    pnl, stats, trades = backtest(df, {'AAA': 'Buy'}, delay=0, max_hold=100, cost=0.0,
                                  sl_atr=1.0, tp_atr=0.0, trail_atr=0.0,
                                  risk_pct=0.01, equity=100000)
    atr_val = atr(df['AAA']['High'], df['AAA']['Low'], df['AAA']['Close']).iloc[-1]
    expected_stop = 100.0 - atr_val * 1.0
    assert trades.iloc[0]['exit_price'] == pytest.approx(expected_stop)
    assert trades.iloc[0]['exit_time'] == df.index[18]


def test_take_profit_hit_intrabar():
    df = _base_df()
    df.loc[df.index[18], ('AAA', 'High')] = 102.0
    pnl, stats, trades = backtest(df, {'AAA': 'Buy'}, delay=0, max_hold=100, cost=0.0,
                                  sl_atr=0.0, tp_atr=1.0, trail_atr=0.0,
                                  risk_pct=0.01, equity=100000)
    atr_val = atr(df['AAA']['High'], df['AAA']['Low'], df['AAA']['Close']).iloc[-1]
    expected_tp = 100.0 + atr_val * 1.0
    assert trades.iloc[0]['exit_price'] == pytest.approx(expected_tp)
    assert trades.iloc[0]['exit_time'] == df.index[18]


def test_trailing_stop_moves_and_hits():
    df = _base_df()
    df.loc[df.index[15], ('AAA', 'High')] = 102.0
    df.loc[df.index[15], ('AAA', 'Low')] = 101.2
    df.loc[df.index[15], ('AAA', 'Close')] = 101.5
    df.loc[df.index[16], ('AAA', 'High')] = 104.0
    df.loc[df.index[16], ('AAA', 'Low')] = 103.2
    df.loc[df.index[16], ('AAA', 'Close')] = 103.5
    df.loc[df.index[17], ('AAA', 'High')] = 103.0
    df.loc[df.index[17], ('AAA', 'Low')] = 102.5
    df.loc[df.index[17], ('AAA', 'Close')] = 102.7
    pnl, stats, trades = backtest(df, {'AAA': 'Buy'}, delay=0, max_hold=100, cost=0.0,
                                  sl_atr=0.0, tp_atr=0.0, trail_atr=1.0,
                                  risk_pct=0.01, equity=100000)
    atr_val = atr(df['AAA']['High'], df['AAA']['Low'], df['AAA']['Close']).iloc[-1]
    trail = 100.0 - atr_val
    trail = max(trail, 102.0 - atr_val)
    trail = max(trail, 104.0 - atr_val)
    expected_exit = trail
    assert trades.iloc[0]['exit_price'] == pytest.approx(expected_exit)
    assert trades.iloc[0]['exit_time'] == df.index[17]
