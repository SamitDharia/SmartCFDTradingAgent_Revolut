import sys
from pathlib import Path


import pandas as pd
import pytest

# Ensure project root is on path
sys.path.append(str(Path(__file__).resolve().parents[1]))


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
