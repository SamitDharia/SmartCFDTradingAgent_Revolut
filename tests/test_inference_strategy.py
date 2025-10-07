import pytest
from unittest.mock import MagicMock, patch, PropertyMock
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
    """Tests that the InferenceStrategy correctly loads a model."""
    model_path = tmp_path / "model.joblib"
    model_path.touch()

    strategy = InferenceStrategy(symbol="BTC/USD", model_path=str(model_path))
    
    mock_joblib_load.assert_called_once_with(model_path)
    assert strategy.model is not None

@patch("smartcfd.strategy.joblib.load")
@patch("smartcfd.strategy.calculate_indicators")
@patch("smartcfd.strategy.DataLoader")
@patch("smartcfd.strategy.Path.exists")
def test_inference_strategy_evaluate(
    mock_path_exists, mock_data_loader, mock_calculate_indicators, mock_joblib_load
):
    """Tests the evaluation logic of the InferenceStrategy by injecting a mock model."""
    # 1. Setup
    # --- Mock file system and model loading ---
    mock_path_exists.return_value = True  # Pretend the model file exists
    mock_model = MagicMock()
    mock_model.predict.return_value = [1]  # Predict 'buy'
    mock_joblib_load.return_value = mock_model # Intercept the model loading

    # --- Mock data loading and feature calculation ---
    mock_df = pd.DataFrame({'close': [100, 110]})
    mock_data_loader.return_value.get_market_data.return_value = mock_df

    mock_features = pd.DataFrame({"feature1": [0.5], "feature2": [0.6]})
    mock_calculate_indicators.return_value = mock_features

    # Instantiate the strategy - this will now call joblib.load due to the mocked Path.exists
    strategy = InferenceStrategy(symbol="BTC/USD", model_path="dummy/path.joblib")

    # 2. Action
    actions = strategy.evaluate(client=MagicMock())

    # 3. Assertions
    mock_joblib_load.assert_called_once_with(strategy.model_path)
    mock_path_exists.assert_called_once()
    mock_data_loader.return_value.get_market_data.assert_called_once()
    mock_calculate_indicators.assert_called_once()
    mock_model.predict.assert_called_once()

    # Verify the action proposed by the strategy
    assert len(actions) == 1
    action = actions[0]
    assert action["action"] == "order"
    assert action["symbol"] == "BTC/USD"
    assert action["decision"] == "buy"
