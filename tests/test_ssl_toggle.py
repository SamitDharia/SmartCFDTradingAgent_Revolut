import sys
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.mark.parametrize("skip", ["0", "1"])
def test_download_smoke(monkeypatch, skip):
    monkeypatch.setenv("SKIP_SSL_VERIFY", skip)
    sys.modules.pop("SmartCFDTradingAgent.pipeline", None)
    sys.modules.pop("SmartCFDTradingAgent.utils.no_ssl", None)

    import SmartCFDTradingAgent.pipeline  # noqa: F401
    import SmartCFDTradingAgent.data_loader as dl

    def fake_download(*args, **kwargs):
        idx = pd.date_range("2024-01-01", periods=1)
        data = {f: [1] for f in [
            "Open",
            "High",
            "Low",
            "Close",
            "Adj Close",
            "Volume",
        ]}
        return pd.DataFrame(data, index=idx)

    monkeypatch.setattr(dl, "_download", fake_download)

    df = dl.get_price_data(["AAPL"], "2024-01-01", "2024-01-02")
    assert not df.empty

    imported = "SmartCFDTradingAgent.utils.no_ssl" in sys.modules
    assert imported == (skip == "1")

