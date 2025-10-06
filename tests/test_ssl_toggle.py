import sys
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.mark.parametrize("skip", ["0", "1"])
def test_download_smoke(monkeypatch, skip):
    # This test is now less about SSL and more about ensuring the data loader can be mocked.
    # The actual SSL verification is handled by the underlying alpaca-py library.
    monkeypatch.setenv("APCA_API_KEY_ID", "mock_key")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "mock_secret")

    import SmartCFDTradingAgent.data_loader as dl
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.models import BarSet

    def fake_get_stock_bars(*args, **kwargs):
        # Create a mock object that has a .df attribute, which is what the data_loader uses.
        class MockBarSet:
            @property
            def df(self):
                idx = pd.to_datetime(pd.date_range("2024-01-01", periods=1, tz="UTC"))
                data = {
                    "open": [150.0],
                    "high": [151.0],
                    "low": [149.0],
                    "close": [150.5],
                    "volume": [100000],
                    "trade_count": [1000],
                    "vwap": [150.2],
                }
                # The real .df is multi-indexed by (symbol, timestamp)
                df = pd.DataFrame(data, index=idx)
                df["symbol"] = "AAPL"
                return df.set_index(["symbol", df.index])

        return MockBarSet()

    monkeypatch.setattr(StockHistoricalDataClient, "get_stock_bars", fake_get_stock_bars)

    # Use the new fetch_and_cache_data function
    output_path = dl.fetch_and_cache_data(
        symbols=["AAPL"],
        start_date="2024-01-01",
        end_date="2024-01-02",
        cache_dir=Path(ROOT) / "tests" / "test_cache" # Use a test-specific cache
    )
    
    assert output_path is not None
    assert output_path.exists()
    
    # Clean up the created cache file if it exists
    if output_path and output_path.exists():
        output_path.unlink()

