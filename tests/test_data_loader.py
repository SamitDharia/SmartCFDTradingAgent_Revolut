import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import pandas as pd
from click.testing import CliRunner

from SmartCFDTradingAgent.data_loader import fetch_and_cache_data, get_data_client
from SmartCFDTradingAgent.__main__ import cli
from alpaca.data.timeframe import TimeFrame

# Set dummy credentials for testing
@pytest.fixture(autouse=True)
def set_test_env():
    os.environ["APCA_API_KEY_ID"] = "test_key"
    os.environ["APCA_API_SECRET_KEY"] = "test_secret"
    yield
    del os.environ["APCA_API_KEY_ID"]
    del os.environ["APCA_API_SECRET_KEY"]

@pytest.fixture
def mock_data_client():
    """Fixture to mock the Alpaca StockHistoricalDataClient."""
    with patch("SmartCFDTradingAgent.data_loader.StockHistoricalDataClient") as mock_client_class:
        mock_client_instance = mock_client_class.return_value
        mock_bars = MagicMock()
        
        data = {
            "timestamp": pd.to_datetime(["2023-01-01 10:00:00", "2023-01-01 10:01:00"]),
            "symbol": ["AAPL", "AAPL"],
            "open": [150.0, 150.1],
            "high": [150.2, 150.3],
            "low": [149.9, 150.0],
            "close": [150.1, 150.2],
            "volume": [1000, 1200],
        }
        sample_df = pd.DataFrame(data).set_index(["symbol", "timestamp"])
        mock_bars.df = sample_df
        
        mock_client_instance.get_stock_bars.return_value = mock_bars
        yield mock_client_instance

def test_fetch_and_cache_data_success(mock_data_client, tmp_path):
    """
    Test successful fetching and caching of data.
    """
    cache_dir = tmp_path / "datasets"
    symbols = ["AAPL"]
    start_date = "2023-01-01"
    end_date = "2023-01-02"

    result_path = fetch_and_cache_data(symbols, start_date, end_date, cache_dir=str(cache_dir))

    assert result_path is not None
    assert result_path.exists()
    
    df = pd.read_parquet(result_path)
    assert not df.empty
    assert "AAPL" in df["symbol"].values
    
    mock_data_client.get_stock_bars.assert_called_once()

def test_fetch_and_cache_data_uses_cache(mock_data_client, tmp_path):
    """
    Test that an existing cache file is used instead of fetching new data.
    """
    cache_dir = tmp_path / "datasets"
    symbols = ["GOOG"]
    start_date = "2023-01-01"
    end_date = "2023-01-02"

    fetch_and_cache_data(symbols, start_date, end_date, cache_dir=str(cache_dir))
    mock_data_client.get_stock_bars.assert_called_once()
    
    mock_data_client.get_stock_bars.reset_mock()

    result_path = fetch_and_cache_data(symbols, start_date, end_date, cache_dir=str(cache_dir))
    
    assert result_path is not None
    mock_data_client.get_stock_bars.assert_not_called()

def test_get_data_client_raises_error_if_no_keys(monkeypatch):
    """
    Test that get_data_client raises a ValueError if API keys are not set.
    """
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    
    with pytest.raises(ValueError, match="Alpaca API keys"):
        get_data_client()

@patch("SmartCFDTradingAgent.__main__.fetch_and_cache_data")
def test_cli_build_dataset_success(mock_fetch, tmp_path):
    """
    Test the 'build-dataset' CLI command for a successful run.
    """
    runner = CliRunner()
    output_file = tmp_path / "test.parquet"
    mock_fetch.return_value = output_file

    result = runner.invoke(
        cli,
        [
            "build-dataset",
            "--symbols", "MSFT",
            "--start-date", "2023-02-01",
            "--end-date", "2023-02-02",
        ],
    )
    
    assert result.exit_code == 0
    assert f"Successfully created dataset: {output_file}" in result.output
    mock_fetch.assert_called_once()

@patch("SmartCFDTradingAgent.__main__.fetch_and_cache_data")
def test_cli_build_dataset_failure(mock_fetch):
    """
    Test the 'build-dataset' CLI command for a failure scenario.
    """
    runner = CliRunner()
    mock_fetch.side_effect = Exception("API limit reached")

    result = runner.invoke(
        cli,
        [
            "build-dataset",
            "--symbols", "TSLA",
            "--start-date", "2023-03-01",
            "--end-date", "2023-03-02",
        ],
    )
    
    assert result.exit_code != 0
    assert "An error occurred: API limit reached" in result.output
