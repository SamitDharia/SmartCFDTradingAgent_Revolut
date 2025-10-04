import pandas as pd
import pytest
import requests

from SmartCFDTradingAgent import data_loader as dl
from SmartCFDTradingAgent.data_loader import get_price_data


def test_get_price_data_logs_missing_warning(monkeypatch, caplog):
    def fake_download(tickers_or_symbol, *_, **__):
        if isinstance(tickers_or_symbol, list):
            raise Exception("batch fail")
        if tickers_or_symbol == "GOOD":
            idx = pd.date_range("2022-01-01", periods=1)
            data = {
                "Open": [1],
                "High": [1],
                "Low": [1],
                "Close": [1],
                "Adj Close": [1],
                "Volume": [1],
            }
            return pd.DataFrame(data, index=idx)
        raise Exception("no data")

    monkeypatch.setattr(
        "SmartCFDTradingAgent.data_loader._download", fake_download
    )

    caplog.set_level("WARNING", logger="SmartCFD")
    get_price_data(["GOOD", "BAD"], "2022-01-01", "2022-01-02", max_tries=1, pause=0)

    assert any("Failed downloads" in r.message for r in caplog.records)
    assert any("BAD" in r.message for r in caplog.records)


def test_get_price_data_cache_hit(monkeypatch, tmp_path, caplog):
    calls = {"n": 0}

    def fake_download(tickers_or_symbol, *_, **__):
        calls["n"] += 1
        idx = pd.date_range("2022-01-01", periods=1, freq="1h")
        data = {
            "Open": [1],
            "High": [1],
            "Low": [1],
            "Close": [1],
            "Adj Close": [1],
            "Volume": [1],
        }
        return pd.DataFrame(data, index=idx)

    monkeypatch.setenv("DATA_CACHE_DIR", str(tmp_path))
    monkeypatch.setattr("SmartCFDTradingAgent.data_loader.CACHE_DIR", tmp_path)
    monkeypatch.setattr("SmartCFDTradingAgent.data_loader._download", fake_download)

    # First call populates cache
    get_price_data(["AAA"], "2022-01-01", "2022-01-02", interval="1h", max_tries=1, pause=0)
    assert calls["n"] == 1

    caplog.set_level("INFO", logger="SmartCFD")
    # Second call should hit cache and not increment calls
    get_price_data(["AAA"], "2022-01-01", "2022-01-02", interval="1h", max_tries=1, pause=0)
    assert calls["n"] == 1
    assert any("Cache hit" in r.message for r in caplog.records)


def test_coinbase_fallback(monkeypatch):
    def fail_download(*_, **__):
        raise Exception("primary download failed")

    def fail_history(*_, **__):
        return None

    def fail_chart(*_, **__):
        return None

    def fake_coinbase(ticker, *, start, end, interval, cache_expire=None):
        idx = pd.date_range(start, periods=2, freq="1h")
        frame = pd.DataFrame(
            {
                "Open": [1.0, 2.0],
                "High": [1.5, 2.5],
                "Low": [0.5, 1.5],
                "Close": [1.2, 2.2],
                "Adj Close": [1.2, 2.2],
                "Volume": [10.0, 20.0],
            },
            index=idx,
        )
        return pd.concat({ticker: frame}, axis=1)

    monkeypatch.setattr("SmartCFDTradingAgent.data_loader._download", fail_download)
    monkeypatch.setattr("SmartCFDTradingAgent.data_loader._download_history", fail_history)
    monkeypatch.setattr("SmartCFDTradingAgent.data_loader._download_chart", fail_chart)
    monkeypatch.setattr("SmartCFDTradingAgent.data_loader._download_coinbase", fake_coinbase)

    df = get_price_data(["BTC-USD"], "2022-01-01", "2022-01-03", interval="1h", max_tries=1, pause=0)

    assert not df.empty
    assert ("BTC-USD", "Close") in df.columns
