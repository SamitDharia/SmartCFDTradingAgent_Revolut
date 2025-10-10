import pandas as pd
from .indicators import (
    atr, rsi, macd, bollinger_bands, adx,
    stochastic_oscillator, volume_profile, price_rate_of_change
)

def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create a rich set of features for the model from historical data.
    This function is canonical and shared by both inference and training.
    """
    if df.empty:
        return pd.DataFrame()

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, utc=True)

    df = df.copy()
    df.columns = [x.lower() for x in df.columns]
    features = pd.DataFrame(index=df.index)

    # Basic returns
    features['feature_return_1m'] = df['close'].pct_change(1)
    features['feature_return_5m'] = df['close'].pct_change(5)
    features['feature_return_15m'] = df['close'].pct_change(15)
    features['feature_return_30m'] = df['close'].pct_change(30)
    features['feature_return_60m'] = df['close'].pct_change(60)

    # Volatility
    features['feature_volatility_5m'] = features['feature_return_1m'].rolling(5).std()
    features['feature_volatility_15m'] = features['feature_return_1m'].rolling(15).std()
    features['feature_volatility_30m'] = features['feature_return_1m'].rolling(30).std()
    features['feature_volatility_60m'] = features['feature_return_1m'].rolling(60).std()

    # Technical Indicators
    features['feature_rsi'] = rsi(df['close'])

    # Stochastic Oscillator
    stoch = stochastic_oscillator(df['high'], df['low'], df['close'])
    features['feature_stoch_k'] = stoch['STOCHk_14_3_3']
    features['feature_stoch_d'] = stoch['STOCHd_14_3_3']

    # MACD
    macd_features = macd(df['close'])
    features['feature_macd'] = macd_features['MACD_12_26_9']
    features['feature_macd_signal'] = macd_features['MACDs_12_26_9']
    features['feature_macd_diff'] = macd_features['MACDh_12_26_9']

    adx_df = adx(df['high'], df['low'], df['close'])
    features['feature_adx'] = adx_df['ADX_14']

    # Bollinger Bands
    bband_features = bollinger_bands(df['close'])
    features['feature_bband_mavg'] = bband_features['BBM_20_2.0']
    features['feature_bband_hband'] = bband_features['BBH_20_2.0']
    features['feature_bband_lband'] = bband_features['BBL_20_2.0']

    # Time-based features
    features['feature_day_of_week'] = df.index.dayofweek
    features['feature_hour_of_day'] = df.index.hour
    features['feature_minute_of_hour'] = df.index.minute

    # Volume Profile (placeholder)
    vp = volume_profile(df['close'], df.get('volume', pd.Series(index=df.index, dtype=float)))
    features = features.join(vp.add_prefix('feature_vp_'))

    # Price Rate of Change
    features['feature_proc'] = price_rate_of_change(df['close'])

    return features

