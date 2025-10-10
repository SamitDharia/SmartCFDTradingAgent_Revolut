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


def macd(series: pd.Series, window_slow: int = 26, window_fast: int = 12, window_sign: int = 9) -> pd.DataFrame:
    """
    Calculate Moving Average Convergence Divergence (MACD).
    Returns a DataFrame with MACD, signal, and histogram.
    """
    macd_indicator = ta.trend.MACD(close=series, window_slow=window_slow, window_fast=window_fast, window_sign=window_sign)
    df = pd.DataFrame()
    df['MACD_12_26_9'] = macd_indicator.macd()
    df['MACDs_12_26_9'] = macd_indicator.macd_signal()
    df['MACDh_12_26_9'] = macd_indicator.macd_diff()
    return df


def bollinger_bands(series: pd.Series, window: int = 20, window_dev: int = 2) -> pd.DataFrame:
    """
    Calculate Bollinger Bands.
    Returns a DataFrame with the middle, high, and low bands.
    """
    bband_indicator = ta.volatility.BollingerBands(close=series, window=window, window_dev=window_dev)
    df = pd.DataFrame()
    df['BBM_20_2.0'] = bband_indicator.bollinger_mavg()
    df['BBH_20_2.0'] = bband_indicator.bollinger_hband()
    df['BBL_20_2.0'] = bband_indicator.bollinger_lband()
    return df


def adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.DataFrame:
    """
    Calculate Average Directional Movement Index (ADX).
    Returns a DataFrame with the ADX value.
    """
    adx_indicator = ta.trend.ADXIndicator(high=high, low=low, close=close, window=window)
    df = pd.DataFrame()
    df[f'ADX_{window}'] = adx_indicator.adx()
    return df


def stochastic_oscillator(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14, smooth_window: int = 3) -> pd.DataFrame:
    """
    Calculate Stochastic Oscillator.
    Returns a DataFrame with %K and %D.
    """
    stoch_indicator = ta.momentum.StochasticOscillator(
        high=high, low=low, close=close, window=window, smooth_window=smooth_window
    )
    df = pd.DataFrame()
    df[f'STOCHk_{window}_{smooth_window}_{smooth_window}'] = stoch_indicator.stoch()
    df[f'STOCHd_{window}_{smooth_window}_{smooth_window}'] = stoch_indicator.stoch_signal()
    return df


def volume_profile(price: pd.Series, volume: pd.Series, bins: int = 10) -> pd.DataFrame:
    """
    A simple volume profile implementation.
    This is a complex indicator and this is a simplified version.
    """
    # This is a placeholder for a more complex implementation
    log.warning("volume_profile is a complex indicator and this is a simplified placeholder.")
    df = pd.DataFrame(index=price.index)
    df['vp_placeholder'] = pd.NA  # Using pd.NA for missing values
    return df


def price_rate_of_change(series: pd.Series, window: int = 12) -> pd.Series:
    """Calculate Price Rate of Change (ROC)."""
    return ta.momentum.roc(close=series, window=window)


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
