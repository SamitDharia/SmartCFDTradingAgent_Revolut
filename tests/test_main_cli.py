import pytest
from click.testing import CliRunner
from unittest.mock import patch

from SmartCFDTradingAgent.__main__ import cli

def test_cli_build_dataset_arguments(monkeypatch):
    """
    Test that the 'build-dataset' command correctly parses arguments
    and calls the data fetching function.
    """
    runner = CliRunner()
    
    # Patch the function that does the actual work
    with patch("SmartCFDTradingAgent.__main__.fetch_and_cache_data") as mock_fetch:
        mock_fetch.return_value = "mock_path" # Simulate successful run
        
        result = runner.invoke(cli, [
            "build-dataset",
            "--symbols", "AAPL,GOOG",
            "--start-date", "2023-01-01",
            "--end-date", "2023-01-02",
            "--timeframe", "1h"
        ])
        
        assert result.exit_code == 0
        assert "Starting data fetch" in result.output
        
        # Verify that the underlying function was called with the correct arguments
        mock_fetch.assert_called_once()
        args, kwargs = mock_fetch.call_args
        assert args[0] == ["AAPL", "GOOG"]
        assert args[1] == "2023-01-01"
        assert args[2] == "2023-01-02"
        # Cannot directly compare timeframe objects, so check the value
        assert kwargs['timeframe'].value == "1H"

def test_cli_help_message():
    """
    Test that the main CLI entrypoint provides a help message.
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Usage: cli [OPTIONS] COMMAND [ARGS]..." in result.output
    assert "build-dataset" in result.output
    assert "engineer-features" in result.output
