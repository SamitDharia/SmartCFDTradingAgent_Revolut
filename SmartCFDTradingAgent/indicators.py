import logging
import pandas as pd
import ta
from ta.utils import dropna
from ta import add_all_ta_features

log = logging.getLogger(__name__)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR).
    A wrapper for the 'ta' library's ATR function to maintain compatibility.
    """
    return ta.volatility.average_true_range(high=high, low=low, close=close, window=window)


def ema(series: pd.Series, window: int = 20) -> pd.Series:
    """Calculate Exponential Moving Average (EMA)."""
    return ta.trend.ema_indicator(close=series, window=window)


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    """Calculate Relative Strength Index (RSI)."""
    return ta.momentum.rsi(close=series, window=window)


def adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    """Calculate Average Directional Movement Index (ADX)."""
    return ta.trend.adx(high=high, low=low, close=close, window=window)


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generates a comprehensive set of technical analysis features for a given OHLCV DataFrame.

    This function processes data for a single symbol at a time.

    Args:
        df: A DataFrame with 'open', 'high', 'low', 'close', 'volume' columns,
            and a datetime index, for a single symbol.

    Returns:
        A new DataFrame with the original data and all generated features.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("Input DataFrame must have a DatetimeIndex.")

    log.info(f"Starting feature engineering on a DataFrame with shape {df.shape}.")

    # Ensure the column names are lowercase for the 'ta' library
    df_processed = df.copy()
    df_processed.columns = [col.lower() for col in df_processed.columns]

    # Use the 'ta' library to add all available technical analysis features
    try:
        df_featured = add_all_ta_features(
            df_processed,
            open="open",
            high="high",
            low="low",
            close="close",
            volume="volume",
            fillna=True  # Fill NaNs that result from indicator calculations
        )
    except Exception as e:
        log.error(f"An error occurred during feature generation: {e}", exc_info=True)
        return df # Return original dataframe on failure

    # --- Add Custom Features ---

    # 1. Returns (log returns are often preferred in financial modeling)
    df_featured['return_1m'] = df_featured['close'].pct_change(1)
    df_featured['return_5m'] = df_featured['close'].pct_change(5)
    df_featured['return_15m'] = df_featured['close'].pct_change(15)

    # 2. Volatility (rolling standard deviation of returns)
    df_featured['volatility_5m'] = df_featured['return_1m'].rolling(window=5).std()
    df_featured['volatility_15m'] = df_featured['return_1m'].rolling(window=15).std()

    # 3. Time-based features from the index
    df_featured['day_of_week'] = df_featured.index.dayofweek
    df_featured['hour_of_day'] = df_featured.index.hour
    df_featured['minute_of_hour'] = df_featured.index.minute
    
    # It's good practice to keep the original column names
    df_featured.columns = [f"feature_{col}" if col not in df.columns else col for col in df_featured.columns]


    log.info(f"Feature engineering complete. New DataFrame shape: {df_featured.shape}.")
    
    return df_featured

def process_all_symbols(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies feature engineering to a multi-symbol DataFrame.

    Args:
        df: A DataFrame with a 'symbol' column and OHLCV data.

    Returns:
        A new DataFrame with features engineered for each symbol.
    """
    if 'symbol' not in df.columns:
        raise ValueError("Input DataFrame must have a 'symbol' column.")
    
    log.info(f"Processing {df['symbol'].nunique()} symbols for feature engineering.")
    
    # Group by symbol and apply the feature creation function
    featured_dfs = df.groupby('symbol').apply(create_features)
    
    # The result might have a multi-index, so we reset it to bring 'symbol' back as a column
    featured_dfs = featured_dfs.reset_index(level=0, drop=True)
    
    return featured_dfs
