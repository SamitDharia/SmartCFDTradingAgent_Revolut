import pytest
import pandas as pd
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from smartcfd.data_loader import is_data_stale, has_data_gaps, has_anomalous_data
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

# --- Fixtures for test data ---

@pytest.fixture
def fresh_data():
    """DataFrame with recent, valid data."""
    now = datetime.utcnow()
    timestamps = pd.to_datetime([now - timedelta(minutes=i) for i in range(10, 0, -1)], utc=True)
    return pd.DataFrame({
        'open': [100 + i for i in range(10)],
        'high': [102 + i for i in range(10)],
        'low': [99 + i for i in range(10)],
        'close': [101 + i for i in range(10)],
        'volume': [1000 + i*10 for i in range(10)]
    }, index=timestamps)

@pytest.fixture
def stale_data():
    """DataFrame with old data."""
    old_time = datetime.utcnow() - timedelta(hours=2)
    timestamps = pd.to_datetime([old_time - timedelta(minutes=i) for i in range(10, 0, -1)], utc=True)
    return pd.DataFrame({'close': [100]*10}, index=timestamps)

@pytest.fixture
def data_with_gaps():
    """DataFrame with a missing timestamp."""
    now = datetime.utcnow()
    timestamps = [
        now - timedelta(minutes=5),
        now - timedelta(minutes=4),
        # Gap here - missing minute 3
        now - timedelta(minutes=2),
        now - timedelta(minutes=1),
    ]
    return pd.DataFrame({'close': [100]*4}, index=pd.to_datetime(timestamps, utc=True))

@pytest.fixture
def data_with_zero_price():
    """DataFrame containing a zero price."""
    now = datetime.utcnow()
    timestamps = pd.to_datetime([now - timedelta(minutes=i) for i in range(4, 0, -1)], utc=True)
    return pd.DataFrame({
        'open': [100, 101, 0, 103],
        'high': [102, 103, 101, 104],
        'low': [99, 100, 98, 102],
        'close': [101, 102, 100, 103],
        'volume': [1000, 1100, 1200, 1300]
    }, index=timestamps)

@pytest.fixture
def data_with_zero_volume_and_price_change():
    """DataFrame with zero volume on a bar with price movement."""
    now = datetime.utcnow()
    timestamps = pd.to_datetime([now - timedelta(minutes=i) for i in range(4, 0, -1)], utc=True)
    return pd.DataFrame({
        'open': [100, 101, 102, 103],
        'high': [102, 103, 104, 105],
        'low': [99, 100, 101, 102],
        'close': [101, 102, 103, 104],
        'volume': [1000, 1100, 0, 1300] # Zero volume on the third bar
    }, index=timestamps)

@pytest.fixture
def data_with_price_spike():
    """DataFrame with a sudden, anomalous price spike."""
    now = datetime.utcnow()
    # Generate 20 periods of normal data
    timestamps = pd.to_datetime([now - timedelta(minutes=i) for i in range(21, 1, -1)], utc=True)
    normal_prices_open = [100 + (i * 0.1) for i in range(20)]
    normal_prices_high = [p + 0.2 for p in normal_prices_open]
    normal_prices_low = [p - 0.2 for p in normal_prices_open]
    normal_prices_close = [p + 0.1 for p in normal_prices_open]

    # Add a spike
    timestamps = timestamps.append(pd.to_datetime([now], utc=True))
    
    prices_open = normal_prices_open + [102]
    # Spike the high value significantly
    prices_high = normal_prices_high + [150] 
    prices_low = normal_prices_low + [101]
    prices_close = normal_prices_close + [149]
    
    return pd.DataFrame({
        'open': prices_open,
        'high': prices_high,
        'low': prices_low,
        'close': prices_close,
        'volume': [1000] * 21
    }, index=timestamps)

# --- Tests for is_data_stale ---

def test_is_data_stale_returns_false_for_fresh_data(fresh_data):
    assert not is_data_stale(fresh_data, max_staleness_minutes=30)

def test_is_data_stale_returns_true_for_stale_data(stale_data):
    assert is_data_stale(stale_data, max_staleness_minutes=60)

def test_is_data_stale_returns_true_for_empty_dataframe():
    assert is_data_stale(pd.DataFrame(), max_staleness_minutes=30)

# --- Tests for has_data_gaps ---

def test_has_data_gaps_returns_false_for_contiguous_data(fresh_data):
    assert not has_data_gaps(fresh_data, TimeFrame(1, TimeFrameUnit.Minute))

def test_has_data_gaps_returns_true_for_data_with_gaps(data_with_gaps):
    assert has_data_gaps(data_with_gaps, TimeFrame(1, TimeFrameUnit.Minute))

def test_has_data_gaps_handles_hourly_data():
    now = datetime.utcnow()
    timestamps = [now - timedelta(hours=3), now - timedelta(hours=1)] # 2-hour gap
    df = pd.DataFrame({'close': [100, 101]}, index=pd.to_datetime(timestamps, utc=True))
    assert has_data_gaps(df, TimeFrame(1, TimeFrameUnit.Hour))

# --- Tests for has_anomalous_data ---

def test_has_anomalous_data_returns_false_for_valid_data(fresh_data):
    assert not has_anomalous_data(fresh_data)

def test_has_anomalous_data_returns_true_for_zero_price(data_with_zero_price):
    assert has_anomalous_data(data_with_zero_price)

def test_has_anomalous_data_returns_true_for_zero_volume_on_price_change(data_with_zero_volume_and_price_change):
    assert has_anomalous_data(data_with_zero_volume_and_price_change)

def test_has_anomalous_data_returns_true_for_price_spike(data_with_price_spike):
    assert has_anomalous_data(data_with_price_spike)

def test_has_anomalous_data_returns_true_for_empty_dataframe():
    assert has_anomalous_data(pd.DataFrame())
