import os
import pandas as pd
import requests
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
import logging
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

def _parse_interval(interval_str: str) -> TimeFrame:
    """Parses a string like '15m', '1h', '1d', '1Hour', '1Day' into an Alpaca TimeFrame."""
    try:
        # More robust parsing
        import re
        match = re.match(r"(\d+)\s*([a-zA-Z]+)", interval_str)
        if not match:
            raise ValueError(f"Invalid interval format: {interval_str}")

        amount = int(match.group(1))
        unit_str = match.group(2).lower()

        unit_map = {
            'm': TimeFrameUnit.Minute, 'min': TimeFrameUnit.Minute, 'minute': TimeFrameUnit.Minute,
            'h': TimeFrameUnit.Hour, 'hr': TimeFrameUnit.Hour, 'hour': TimeFrameUnit.Hour,
            'd': TimeFrameUnit.Day, 'day': TimeFrameUnit.Day,
        }

        unit = None
        for k, v in unit_map.items():
            if unit_str.startswith(k):
                unit = v
                break

        if not unit:
            raise ValueError(f"Invalid time unit in interval: {interval_str}")

        return TimeFrame(amount, unit)
    except (ValueError, IndexError) as e:
        log.error("data_loader.parse_interval.fail", extra={"extra": {"interval": interval_str, "error": repr(e)}})
        # Default to a sensible value if parsing fails, to avoid crashing.
        return TimeFrame.Minute

class DataLoader:
    """
    Handles fetching historical market data from Alpaca.
    """
    def __init__(self, api_base: str = None):
        # api_base is not directly used by CryptoHistoricalDataClient,
        # but it's good practice for consistency.
        self.client = CryptoHistoricalDataClient()
        # HACK: Disable SSL verification for corporate proxies.
        # The session object is part of the underlying REST client.
        self.client._session.verify = False

    def fetch_historical_range(self, symbol: str, start_date: str, end_date: str, interval: str) -> pd.DataFrame | None:
        """
        Fetches historical crypto data for a single symbol between two dates.
        """
        log.info(f"Fetching historical data for {symbol} from {start_date} to {end_date}")
        try:
            timeframe = _parse_interval(interval)
            request = CryptoBarsRequest(
                symbol_or_symbols=[symbol],
                timeframe=timeframe,
                start=pd.to_datetime(start_date).tz_localize('UTC'),
                end=pd.to_datetime(end_date).tz_localize('UTC')
            )
            bars = self.client.get_crypto_bars(request)
            df = bars.df

            # If the symbol is in a multi-index, extract it
            if isinstance(df.index, pd.MultiIndex):
                if 'symbol' in df.index.names and not df.index.get_level_values('symbol').empty:
                    if symbol in df.index.get_level_values('symbol'):
                        df = df.loc[symbol]
                    else:
                        log.warning(f"Symbol {symbol} not found in fetched multi-index data.")
                        return pd.DataFrame()
                else:
                    pass # Assume single-symbol response

            log.info(f"Successfully fetched {len(df)} bars for {symbol}")
            return df
        except Exception as e:
            log.error(f"Failed to fetch historical data for {symbol}: {e}", exc_info=True)
            return pd.DataFrame()

    def get_market_data(self, symbols: list[str], interval: str, limit: int) -> pd.DataFrame | None:
        """
        Fetches historical crypto data for a list of symbols.
        """
        if not symbols:
            return None
            
        try:
            timeframe = _parse_interval(interval)
            # Calculate start time based on limit. This is an approximation.
            # For a more precise calculation, one would need to consider market hours,
            # but for crypto 24/7, this is a reasonable estimate.
            if timeframe.unit == TimeFrameUnit.Minute:
                delta = timedelta(minutes=timeframe.amount * limit)
            elif timeframe.unit == TimeFrameUnit.Hour:
                delta = timedelta(hours=timeframe.amount * limit)
            elif timeframe.unit == TimeFrameUnit.Day:
                delta = timedelta(days=timeframe.amount * limit)
            else:
                delta = timedelta(days=limit) # Fallback

            # Fetch a bit more data to ensure we have enough bars
            start_dt = datetime.utcnow() - (delta * 1.2)

            request = CryptoBarsRequest(
                symbol_or_symbols=symbols,
                timeframe=timeframe,
                start=start_dt
            )
            bars = self.client.get_crypto_bars(request)
            df = bars.df.reset_index()
            df = df.rename(columns={'timestamp': 'time'})
            
            # Alpaca returns data for each symbol. We need to process it.
            # For now, let's assume we only get one symbol at a time for simplicity,
            # as the current usage pattern suggests.
            if isinstance(df.index, pd.MultiIndex):
                 if symbols[0] in df.index.get_level_values('symbol'):
                    df = df.loc[symbols[0]]
                 else:
                    return None
            
            df = df.set_index('time')
            return df

        except Exception as e:
            log.error("data_loader.get_market_data.fail", extra={"extra": {"symbols": symbols, "error": repr(e)}})
            return None


def fetch_data(symbol: str, timeframe: TimeFrame, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Fetches historical crypto data for a single symbol between two dates.
    """
    log.info(f"Fetching data for {symbol} from {start_date} to {end_date}")
    client = CryptoHistoricalDataClient()
    # HACK: Disable SSL verification for corporate proxies.
    client._session.verify = False
    try:
        request = CryptoBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=timeframe,
            start=pd.to_datetime(start_date).tz_localize('UTC'),
            end=pd.to_datetime(end_date).tz_localize('UTC')
        )
        bars = client.get_crypto_bars(request)
        df = bars.df
        
        # If the symbol is in a multi-index, extract it
        if isinstance(df.index, pd.MultiIndex):
            # Check if the symbol level exists and is not empty
            if 'symbol' in df.index.names and not df.index.get_level_values('symbol').empty:
                 if symbol in df.index.get_level_values('symbol'):
                    df = df.loc[symbol]
                 else:
                    log.warning(f"Symbol {symbol} not found in fetched multi-index data.")
                    return pd.DataFrame()
            else:
                # If there's no symbol index, we assume it's a single-symbol response
                pass

        log.info(f"Successfully fetched {len(df)} bars for {symbol}")
        return df
    except Exception as e:
        log.error(f"Failed to fetch data for {symbol}: {e}", exc_info=True)
        return pd.DataFrame()

# --- Data Integrity Checks ---

def is_data_stale(df: pd.DataFrame, max_staleness_minutes: int) -> bool:
    """
    Checks if the latest data point is older than the allowed maximum staleness.
    """
    if df.empty:
        log.warning("Data integrity check failed: DataFrame is empty.")
        return True
    
    latest_timestamp = df.index.max()
    # Ensure latest_timestamp is timezone-aware (UTC)
    if latest_timestamp.tzinfo is None:
        latest_timestamp = latest_timestamp.tz_localize('UTC')

    staleness = datetime.now(timezone.utc) - latest_timestamp
    
    is_stale = staleness > timedelta(minutes=max_staleness_minutes)
    if is_stale:
        log.warning(f"Data is stale. Last update was {staleness.total_seconds() / 60:.2f} minutes ago (threshold: {max_staleness_minutes} mins).")
    
    return is_stale

def has_data_gaps(df: pd.DataFrame, expected_interval: TimeFrame) -> bool:
    """
    Checks for missing timestamps in the data, indicating gaps.
    """
    if len(df) < 2:
        return False  # Not enough data to detect a gap.

    # Convert Alpaca TimeFrame to pandas frequency string
    if expected_interval.unit == TimeFrameUnit.Minute:
        freq_str = f"{expected_interval.amount}min"
    elif expected_interval.unit == TimeFrameUnit.Hour:
        freq_str = f"{expected_interval.amount}h"
    elif expected_interval.unit == TimeFrameUnit.Day:
        freq_str = f"{expected_interval.amount}D"
    else:
        log.warning(f"Unsupported timeframe unit for gap detection: {expected_interval.unit}")
        return False

    # Ensure index is sorted
    df = df.sort_index()
    
    # Use the generated frequency string
    expected_timestamps = pd.date_range(start=df.index.min(), end=df.index.max(), freq=freq_str)
    missing_timestamps = expected_timestamps.difference(df.index)
    
    if not missing_timestamps.empty:
        log.warning(f"Data gap detected. Missing {len(missing_timestamps)} timestamps. First missing: {missing_timestamps[0]}")
        return True
        
    return False

def has_anomalous_data(df: pd.DataFrame, anomaly_threshold: float = 5.0) -> bool:
    """
    Performs basic anomaly detection on the data.
    - Checks for empty or insufficient data.
    - Checks for zero prices.
    - Checks for bars where high != low but volume is zero
    - Checks for sudden price spikes (e.g., > 5x the recent average range).
    """
    if df.empty:
        log.warning("Anomaly detected: DataFrame is empty.")
        return True

    # Standardize column names to lowercase for robustness
    df = df.copy()
    df.columns = [col.lower() for col in df.columns]

    # Check for zero prices in key columns
    if (df[['open', 'high', 'low', 'close']] <= 0).any().any():
        log.warning("Anomaly detected: Zero or negative price found in OHLC data.")
        return True

    if has_zero_volume_anomaly(df):
        return True

    # Check for sudden price spikes
    df['range'] = df['high'] - df['low']
    
    # Avoid the most recent bar in the average calculation to detect its anomaly
    average_range = df['range'].iloc[:-1].mean()
    latest_range = df['range'].iloc[-1]

    # Check for division by zero or near-zero
    if average_range > 1e-9 and (latest_range / average_range) > anomaly_threshold:
        log.warning(f"Anomaly detected: Sudden price spike. Latest range ({latest_range:.2f}) is more than {anomaly_threshold}x the average range ({average_range:.2f}).")
        return True

    return False

def has_zero_volume_anomaly(df: pd.DataFrame) -> bool:
    """
    Checks for bars where high != low but volume is zero.
    """
    if 'high' in df.columns and 'low' in df.columns and 'volume' in df.columns:
        if ((df['high'] != df['low']) & (df['volume'] == 0)).any():
            log.warning("Anomaly detected: Zero volume found on a bar with price movement.")
            return True
    return False
