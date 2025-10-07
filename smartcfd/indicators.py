import logging
import pandas as pd
import ta
from ta.utils import dropna

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

    # --- Add Custom and Specific TA Features ---

    # 1. Bollinger Bands
    bband = ta.volatility.BollingerBands(close=df_processed['close'], window=20, window_dev=2)
    df_processed['bband_mavg'] = bband.bollinger_mavg()
    df_processed['bband_hband'] = bband.bollinger_hband()
    df_processed['bband_lband'] = bband.bollinger_lband()

    # 2. MACD
    macd = ta.trend.MACD(close=df_processed['close'], window_slow=26, window_fast=12, window_sign=9)
    df_processed['macd'] = macd.macd()
    df_processed['macd_signal'] = macd.macd_signal()
    df_processed['macd_diff'] = macd.macd_diff()

    # 3. Stochastic Oscillator
    stoch = ta.momentum.StochasticOscillator(high=df_processed['high'], low=df_processed['low'], close=df_processed['close'], window=14, smooth_window=3)
    df_processed['stoch_k'] = stoch.stoch()
    df_processed['stoch_d'] = stoch.stoch_signal()

    # --- Existing Custom Features ---

    # Returns (log returns are often preferred in financial modeling)
    df_processed['return_1m'] = df_processed['close'].pct_change(1)
    df_processed['return_5m'] = df_processed['close'].pct_change(5)
    df_processed['return_15m'] = df_processed['close'].pct_change(15)

    # Volatility (rolling standard deviation of returns)
    df_processed['volatility_5m'] = df_processed['return_1m'].rolling(window=5).std()
    df_processed['volatility_15m'] = df_processed['return_1m'].rolling(window=15).std()

    # Time-based features from the index
    df_processed['day_of_week'] = df_processed.index.dayofweek
    df_processed['hour_of_day'] = df_processed.index.hour
    df_processed['minute_of_hour'] = df_processed.index.minute
    
    # It's good practice to keep the original column names
    df_processed.columns = [f"feature_{col}" if col not in df.columns else col for col in df_processed.columns]


    log.info(f"Feature engineering complete. New DataFrame shape: {df_processed.shape}.")
    
    return df_processed

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
