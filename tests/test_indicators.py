import pytest
import pandas as pd
import numpy as np
from click.testing import CliRunner
from pathlib import Path

from SmartCFDTradingAgent.indicators import create_features, process_all_symbols
from SmartCFDTradingAgent.__main__ import cli

@pytest.fixture
def sample_ohlcv_df():
    """Creates a sample DataFrame for a single symbol."""
    dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=100, freq="T"))
    data = {
        "open": np.random.uniform(98, 102, size=100),
        "high": np.random.uniform(100, 105, size=100),
        "low": np.random.uniform(95, 100, size=100),
        "close": np.random.uniform(99, 103, size=100),
        "volume": np.random.randint(1000, 5000, size=100),
    }
    df = pd.DataFrame(data, index=dates)
    # Ensure high is always >= open and close, and low is always <= open and close
    df['high'] = df[['high', 'open', 'close']].max(axis=1)
    df['low'] = df[['low', 'open', 'close']].min(axis=1)
    return df

@pytest.fixture
def multi_symbol_df(sample_ohlcv_df):
    """Creates a sample DataFrame for multiple symbols."""
    df1 = sample_ohlcv_df.copy()
    df1['symbol'] = 'AAPL'
    
    df2 = sample_ohlcv_df.copy()
    df2['symbol'] = 'GOOG'
    
    return pd.concat([df1.reset_index(), df2.reset_index()]).rename(columns={'index': 'timestamp'})

def test_create_features_single_symbol(sample_ohlcv_df):
    """
    Test that feature creation works for a single-symbol DataFrame.
    """
    featured_df = create_features(sample_ohlcv_df)
    
    assert isinstance(featured_df, pd.DataFrame)
    # Check if some expected feature columns were added
    assert "feature_momentum_rsi" in featured_df.columns
    assert "feature_return_5m" in featured_df.columns
    assert "feature_day_of_week" in featured_df.columns
    # Check that the number of rows remains the same
    assert len(featured_df) == len(sample_ohlcv_df)

def test_process_all_symbols(multi_symbol_df):
    """
    Test that feature engineering works correctly for a multi-symbol DataFrame.
    """
    # Set timestamp as index for processing
    df = multi_symbol_df.set_index('timestamp')
    
    featured_df = process_all_symbols(df)
    
    assert isinstance(featured_df, pd.DataFrame)
    assert 'symbol' in featured_df.columns
    
    # Check that features were created for both symbols
    assert featured_df['symbol'].nunique() == 2
    assert "feature_trend_macd_signal" in featured_df.columns
    
    # Check that the total number of rows is correct
    assert len(featured_df) == len(multi_symbol_df)

def test_cli_engineer_features(multi_symbol_df, tmp_path):
    """
    Test the 'engineer-features' CLI command.
    """
    runner = CliRunner()
    
    input_file = tmp_path / "input_dataset.parquet"
    multi_symbol_df.to_parquet(input_file)

    output_file = tmp_path / "input_dataset_featured.parquet"

    result = runner.invoke(
        cli,
        ["engineer-features", str(input_file)]
    )
    
    assert result.exit_code == 0
    assert "Successfully created featured dataset" in result.output
    assert output_file.exists()
    
    # Verify the contents of the output file
    featured_df = pd.read_parquet(output_file)
    assert "feature_momentum_stoch_rsi" in featured_df.columns
    assert featured_df['symbol'].nunique() == 2
