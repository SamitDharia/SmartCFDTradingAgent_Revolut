import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
import pandas as pd
from pathlib import Path

from SmartCFDTradingAgent.__main__ import cli

@pytest.fixture
def runner():
    return CliRunner()

def test_cli_train_model(runner, tmp_path):
    """
    Test the 'train-model' command.
    """
    # 1. Create a dummy features file
    features_dir = tmp_path / "features"
    features_dir.mkdir()
    features_file = features_dir / "test_features.parquet"
    
    dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=100, freq="min"))
    data = {
        "symbol": ["AAPL"] * 100,
        "open": [150 + i for i in range(100)],
        "high": [151 + i for i in range(100)],
        "low": [149 + i for i in range(100)],
        "close": [150.5 + i for i in range(100)],
        "volume": [100000 + i * 100 for i in range(100)],
        "rsi": [50.0] * 100,
        "ema_20": [150.0] * 100,
    }
    df = pd.DataFrame(data, index=dates)
    df.index.name = "timestamp"
    df.reset_index(inplace=True)
    df.to_parquet(features_file)

    # 2. Define the output path for the model
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    model_file = model_dir / "test_model.joblib"

    # 3. Run the CLI command
    result = runner.invoke(cli, [
        "train-model",
        str(features_file),
        "--output-file", str(model_file)
    ])

    # 4. Assert the results
    assert result.exit_code == 0
    assert "Model training complete" in result.output
    assert model_file.exists()
