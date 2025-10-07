import pytest
import pandas as pd
import numpy as np

from smartcfd.regime_detector import RegimeDetector, MarketRegime

@pytest.fixture
def regime_detector():
    """Provides a default RegimeDetector for tests."""
    return RegimeDetector(short_window=5, long_window=20)

def generate_test_data(base_price, atr_val, periods):
    """Generates a DataFrame with specified price characteristics."""
    dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=periods, freq="15min"))
    
    high_prices = base_price + np.random.uniform(0, atr_val, periods)
    low_prices = base_price - np.random.uniform(0, atr_val, periods)
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
    
    return df

def test_detect_regime_low_volatility(regime_detector):
    """Tests that a low volatility regime is correctly detected."""
    # Generate data where short-term and long-term volatility are similar
    data = generate_test_data(base_price=100, atr_val=2, periods=100)
    
    regime = regime_detector.detect_regime(data)
    assert regime == MarketRegime.LOW_VOLATILITY

def test_detect_regime_high_volatility(regime_detector):
    """Tests that a high volatility regime is correctly detected."""
    # Generate stable data for the long window
    long_data = generate_test_data(base_price=100, atr_val=2, periods=80)
    
    # Generate volatile data for the short window
    short_data = generate_test_data(base_price=100, atr_val=5, periods=20)
    
    # Combine them
    data = pd.concat([long_data, short_data])
    
    regime = regime_detector.detect_regime(data)
    assert regime == MarketRegime.HIGH_VOLATILITY

def test_detect_regime_insufficient_data(regime_detector):
    """Tests that the regime is UNDEFINED if there is not enough data."""
    # Long window is 20, so 19 periods is not enough
    data = generate_test_data(base_price=100, atr_val=2, periods=19)
    
    regime = regime_detector.detect_regime(data)
    assert regime == MarketRegime.UNDEFINED

def test_detect_regime_none_data(regime_detector):
    """Tests that the regime is UNDEFINED if the data is None."""
    regime = regime_detector.detect_regime(None)
    assert regime == MarketRegime.UNDEFINED

def test_init_invalid_windows():
    """Tests that the constructor raises an error for invalid window sizes."""
    with pytest.raises(ValueError):
        # short_window is not less than long_window
        RegimeDetector(short_window=20, long_window=20)
    
    with pytest.raises(ValueError):
        # short_window is greater than long_window
        RegimeDetector(short_window=30, long_window=20)
