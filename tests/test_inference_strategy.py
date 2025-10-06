import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import pandas as pd
import joblib
import time

from smartcfd.strategy import InferenceStrategy

# A simple class to act as a mock model that can be pickled
class PickleableMockModel:
    def __init__(self):
        self.feature_names_in_ = ["feature1", "feature2"]
        self.predict = MagicMock(return_value=[1])
        self.predict_proba = MagicMock(return_value=[[0.1, 0.9]]) # Corresponds to a 'buy' signal

@pytest.fixture
def mock_model():
    """Creates a mock XGBoost model that is pickleable."""
    return PickleableMockModel()

@pytest.fixture
def mock_alpaca_client():
    """Creates a mock Alpaca client."""
    client = MagicMock()
    bars = [
        {"t": "2023-01-01T00:00:00Z", "o": 100, "h": 102, "l": 99, "c": 101, "v": 1000},
        {"t": "2023-01-02T00:00:00Z", "o": 101, "h": 103, "l": 100, "c": 102, "v": 1200},
    ]
    client.get_bars.return_value = bars
    return client

@patch("joblib.load")
def test_inference_strategy_model_loading(mock_joblib_load, tmp_path):
    """Tests that the InferenceStrategy correctly loads the latest model."""
    # 1. Setup
    storage_path = tmp_path / "storage"
    storage_path.mkdir()

    # Create dummy files, the content doesn't matter as joblib.load is mocked
    model_path1 = storage_path / "model__BTCUSD__20230101.joblib"
    model_path2 = storage_path / "model__BTCUSD__20230102.joblib"
    model_path1.touch()
    time.sleep(0.1) # Ensure mtime is different
    model_path2.touch()

    # 2. Action
    with patch("smartcfd.strategy.STORAGE_PATH", storage_path):
        strategy = InferenceStrategy(symbol="BTC/USD")

    # 3. Assert
    assert strategy.model is not None
    assert strategy.model_path == model_path2
    mock_joblib_load.assert_called_once_with(model_path2)


@patch("smartcfd.strategy.calculate_indicators")
def test_inference_strategy_evaluate(mock_calculate_indicators, mock_model, mock_alpaca_client):
    """Tests the evaluation logic of the InferenceStrategy by injecting a mock model."""
    # 1. Setup
    mock_calculate_indicators.return_value = pd.DataFrame({
        "feature1": [0.5], "feature2": [0.6]
    })

    # Instantiate the strategy and directly inject the mock model
    strategy = InferenceStrategy(symbol="BTC/USD", model=mock_model)

    # 2. Action
    actions = strategy.evaluate(mock_alpaca_client)

    # 3. Assert
    assert len(actions) == 1
    action = actions[0]
    assert action["action"] == "log"
    assert action["symbol"] == "BTC/USD"
    assert action["decision"] == "buy"
    assert action["reason"] == "inference"
    
    mock_alpaca_client.get_bars.assert_called_once()
    mock_calculate_indicators.assert_called_once()
    
    # Assert that the methods on our injected mock model were called
    mock_model.predict.assert_called_once()
    mock_model.predict_proba.assert_called_once()
