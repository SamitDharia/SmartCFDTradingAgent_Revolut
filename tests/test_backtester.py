import pytest
import pandas as pd
import joblib
from pathlib import Path
import xgboost as xgb

from SmartCFDTradingAgent.backtester import Backtester

@pytest.fixture
def dummy_model_and_data(tmp_path):
    """Creates a dummy model and dummy feature data for testing."""
    # 1. Create dummy data
    features_dir = tmp_path / "features"
    features_dir.mkdir()
    features_file = features_dir / "test_features.parquet"
    
    dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=10, freq="min"))
    data = {
        "symbol": ["AAPL"] * 10,
        "open": [150, 151, 152, 153, 154, 155, 156, 157, 158, 159],
        "high": [151, 152, 153, 154, 155, 156, 157, 158, 159, 160],
        "low": [149, 150, 151, 152, 153, 154, 155, 156, 157, 158],
        "close": [150.5, 151.5, 152.5, 153.5, 154.5, 155.5, 156.5, 157.5, 158.5, 159.5],
        "volume": [100000] * 10,
        "feature1": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
        "feature2": [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1],
    }
    df = pd.DataFrame(data, index=dates)
    df.index.name = "timestamp"
    df.reset_index(inplace=True)
    df.to_parquet(features_file)

    # 2. Create a dummy model
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    model_file = model_dir / "test_model.joblib"
    
    # Create a simple, predictable model
    X = pd.DataFrame({'feature1': [0.1, 0.9], 'feature2': [0.9, 0.1]})
    y = [0, 1]
    model = xgb.XGBClassifier(objective='binary:logistic', use_label_encoder=False)
    model.fit(X, y)
    
    joblib.dump(model, model_file)
    
    return model_file, features_file

def test_backtester_initialization(dummy_model_and_data):
    """Test that the Backtester initializes correctly."""
    model_path, _ = dummy_model_and_data
    backtester = Backtester(model_path=str(model_path), initial_cash=5000)
    assert backtester.initial_cash == 5000
    assert backtester.cash == 5000
    assert backtester.model is not None

def test_backtester_run_simple(dummy_model_and_data):
    """Test a simple run of the backtester."""
    model_path, features_path = dummy_model_and_data
    
    features_df = pd.read_parquet(features_path)
    # The backtester expects timestamp as a column, not an index.
    # features_df = features_df.set_index('timestamp')

    backtester = Backtester(model_path=str(model_path), initial_cash=10000)
    # Use a very low threshold to ensure a trade is triggered
    results = backtester.run(features_df, signal_threshold=0.1) 

    assert results is not None
    assert "final_cash" in results
    assert "total_return_pct" in results
    assert "num_trades" in results
    
    # Based on the dummy model, it should buy on high feature1 and sell on the next bar.
    # Let's trace the logic.
    assert results["num_trades"] > 0
    
    trades_df = results["trades"]
    assert not trades_df.empty
    assert "buy" in trades_df["side"].values
    assert "sell" in trades_df["side"].values

    equity_curve = results["equity_curve"]
    assert not equity_curve.empty
    assert "equity" in equity_curve.columns
