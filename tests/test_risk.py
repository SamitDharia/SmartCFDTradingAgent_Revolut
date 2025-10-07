import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from smartcfd.risk import RiskManager
from smartcfd.config import RiskConfig

@pytest.fixture
def risk_config():
    """Provides a default RiskConfig for tests."""
    return RiskConfig(
        max_daily_drawdown_percent=-5.0,
        max_total_exposure_percent=50.0,
        max_exposure_per_asset_percent=25.0,
        risk_per_trade_percent=1.0,
        circuit_breaker_atr_multiplier=3.0,
    )

@pytest.fixture
def risk_manager(risk_config):
    """Provides a RiskManager instance for tests."""
    portfolio_manager = MagicMock()
    return RiskManager(portfolio_manager, risk_config)

@pytest.fixture
def historical_data():
    """
    Provides a DataFrame with historical data for tests.
    The data simulates a stable period followed by a sudden volatility spike.
    """
    # Generate 100 data points with stable ATR
    base_price = 100
    stable_atr_val = 2
    dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=100, freq="15min"))
    
    # Create a DataFrame with somewhat realistic price movements
    high_prices = base_price + np.random.uniform(0, stable_atr_val, 100)
    low_prices = base_price - np.random.uniform(0, stable_atr_val, 100)
    close_prices = (high_prices + low_prices) / 2
    
    data = {
        'High': high_prices,
        'Low': low_prices,
        'Close': close_prices,
    }
    df = pd.DataFrame(data, index=dates)
    
    # Ensure High is always >= Low
    df['High'] = df[['High', 'Low']].max(axis=1)
    df['Low'] = df[['High', 'Low']].min(axis=1)

    # Add a sudden spike in the last period to trigger the breaker
    spike_multiplier = 5
    df.iloc[-1, df.columns.get_loc('High')] = base_price + (stable_atr_val * spike_multiplier)
    df.iloc[-1, df.columns.get_loc('Low')] = base_price - (stable_atr_val * spike_multiplier)
    df.iloc[-1, df.columns.get_loc('Close')] = base_price
    
    return df

def test_is_drawdown_exceeded(risk_manager):
    """Test if drawdown is correctly identified as exceeded."""
    with patch('smartcfd.risk.get_daily_pnl', return_value=-600):
        assert risk_manager.is_drawdown_exceeded(10000)

def test_is_drawdown_not_exceeded(risk_manager):
    """Test if drawdown is correctly identified as not exceeded."""
    with patch('smartcfd.risk.get_daily_pnl', return_value=-400):
        assert not risk_manager.is_drawdown_exceeded(10000)

def test_is_volatility_too_high_disabled(risk_manager, historical_data):
    """Test that the volatility check is skipped if the multiplier is zero."""
    risk_manager.config.circuit_breaker_atr_multiplier = 0
    assert not risk_manager.is_volatility_too_high(historical_data, "BTC/USD")

def test_is_volatility_too_high_normal(risk_manager, historical_data):
    """Test that volatility is not considered too high under normal conditions."""
    # Use the historical data but remove the last row which contains the spike
    normal_data = historical_data.iloc[:-1].copy()
    assert not risk_manager.is_volatility_too_high(normal_data, "BTC/USD")

def test_is_volatility_too_high_triggered(risk_manager, historical_data):
    """Test that the circuit breaker is triggered during a volatility spike."""
    assert risk_manager.is_volatility_too_high(historical_data, "BTC/USD")

def test_is_volatility_too_high_insufficient_data(risk_manager):
    """Test that the breaker is not tripped with insufficient data."""
    # Create a small DataFrame
    short_data = pd.DataFrame({
        'High': [100, 101],
        'Low': [99, 100],
        'Close': [100.5, 100.5]
    }, index=pd.to_datetime(['2023-01-01 09:00', '2023-01-01 09:15']))
    
    assert not risk_manager.is_volatility_too_high(short_data, "BTC/USD")
