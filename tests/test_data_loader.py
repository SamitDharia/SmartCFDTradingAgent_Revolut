import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure project root is on path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from SmartCFDTradingAgent import data_loader


# Mock helpers

def fake_download_intraday(symbol, *, period=None, start=None, end=None, interval=None, threads=True):
    idx = pd.date_range("2020-01-01", periods=2)
    data = pd.DataFrame(
        {
            "Open": [1.0, 2.0],
            "High": [2.0, 3.0],
            "Low": [0.5, 1.5],
            "Close": [1.5, 2.5],
            "Adj Close": [1.5, 2.5],
            "Volume": [100, 200],
        },
        index=idx,
    )
    return data


def fake_download_daily(tickers, *, period=None, start=None, end=None, interval=None, threads=True):
    if not isinstance(tickers, (list, tuple)):
        tickers = [tickers]
    idx = pd.date_range("2020-01-01", periods=2)
    cols = pd.MultiIndex.from_product([tickers, data_loader.FIELDS_ORDER])
    data = pd.DataFrame(
        np.arange(len(idx) * len(cols)).reshape(len(idx), len(cols)),
        index=idx,
        columns=cols,
    )
    return data


def test_get_price_data_intraday(monkeypatch):
    monkeypatch.setattr(data_loader, "_download", fake_download_intraday)
    df = data_loader.get_price_data(["AAA"], "2020-01-01", "2020-01-02", interval="1h")
    assert isinstance(df.columns, pd.MultiIndex)
    assert ("AAA", "Close") in df.columns


def test_get_price_data_daily(monkeypatch):
    monkeypatch.setattr(data_loader, "_download", fake_download_daily)
    df = data_loader.get_price_data(["AAA", "BBB"], "2020-01-01", "2020-01-02", interval="1d")
    assert isinstance(df.columns, pd.MultiIndex)
    assert ("AAA", "Close") in df.columns
    assert ("BBB", "Close") in df.columns
