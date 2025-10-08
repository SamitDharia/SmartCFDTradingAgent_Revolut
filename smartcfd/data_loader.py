import os
import pandas as pd
import requests
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest, CryptoSnapshotRequest, CryptoSnapshotRequest, CryptoSnapshotRequest, CryptoSnapshotRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict
from typing import Dict
from typing import Dict

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

    def get_market_data(self, symbols: list[str], interval: str, limit: int) -> Dict[str, pd.DataFrame]:
        """
        Fetches and validates historical crypto data for a list of symbols.
        This method combines historical bars with the latest snapshot to ensure data is fresh
        and complete, avoiding partial bars for the current interval.
        """
        if not symbols:
            return {}

        try:
            timeframe = _parse_interval(interval)
            # Calculate start time for historical data fetch
            if timeframe.unit == TimeFrameUnit.Minute:
                delta = timedelta(minutes=timeframe.amount * limit)
            elif timeframe.unit == TimeFrameUnit.Hour:
                delta = timedelta(hours=timeframe.amount * limit)
            elif timeframe.unit == TimeFrameUnit.Day:
                delta = timedelta(days=timeframe.amount * limit)
            else:
                # Fallback for less common timeframes
                delta = timedelta(days=limit) 
            
            start_dt = datetime.utcnow() - (delta * 1.2) # Fetch slightly more to be safe

            # 1. Fetch historical bars
            bars_request = CryptoBarsRequest(
                symbol_or_symbols=symbols,
                timeframe=timeframe,
                start=start_dt
            )
            bars_df = self.client.get_crypto_bars(bars_request).df

            # 2. Fetch latest snapshot data
            snapshot_request = CryptoSnapshotRequest(symbol_or_symbols=symbols)
            snapshots = self.client.get_crypto_snapshot(snapshot_request)

            # --- Data Combination and Validation ---
            validated_data = {}
            for symbol in symbols:
                # Extract historical data for the specific symbol
                if isinstance(bars_df.index, pd.MultiIndex) and symbol in bars_df.index.get_level_values('symbol'):
                    symbol_df = bars_df.loc[symbol].copy()
                elif not isinstance(bars_df.index, pd.MultiIndex) and len(symbols) == 1:
                    symbol_df = bars_df.copy()
                else:
                    log.warning(f"data_loader.get_market_data.no_hist_data", extra={"extra": {"symbol": symbol}})
                    symbol_df = pd.DataFrame() # Start with an empty frame

                # Get the corresponding snapshot
                snapshot = snapshots.get(symbol)
                if not snapshot or not snapshot.latest_bar:
                    log.warning(f"data_loader.get_market_data.no_snapshot", extra={"extra": {"symbol": symbol}})
                    validated_data[symbol] = pd.DataFrame() # Invalidate if no snapshot
                    continue

                # Create a DataFrame from the snapshot's bar
                snapshot_bar_dict = snapshot.latest_bar.dict()
                snapshot_df = pd.DataFrame([snapshot_bar_dict])
                snapshot_df['timestamp'] = pd.to_datetime(snapshot_df['timestamp'])
                snapshot_df = snapshot_df.set_index('timestamp')

                # Combine historical with snapshot to get the most accurate recent bar
                if not symbol_df.empty:
                    # If the last historical bar has the same timestamp as the snapshot, it's a partial bar.
                    # We replace it with the more up-to-date snapshot bar.
                    if symbol_df.index[-1] == snapshot_df.index[0]:
                        symbol_df = symbol_df.iloc[:-1]
                    
                    # Append the snapshot bar
                    symbol_df = pd.concat([symbol_df, snapshot_df])
                else:
                    # If no historical data, start with the snapshot
                    symbol_df = snapshot_df

                # --- Data Integrity Validation ---
                is_stale_flag = is_data_stale(symbol_df, max_staleness_minutes=timeframe.amount * 5)
                gaps_found = has_data_gaps(symbol_df, expected_interval=timeframe)
                is_anomalous = has_anomalous_data(symbol_df)

                if is_stale_flag or gaps_found or is_anomalous:
                    log.warning(f"data_loader.get_market_data.validation_failed", extra={"extra": {"symbol": symbol, "stale": is_stale_flag, "gaps": gaps_found, "anomalous": is_anomalous}})
                    validated_data[symbol] = pd.DataFrame()
                else:
                    # Ensure we only return the last 'limit' bars
                    validated_data[symbol] = symbol_df.tail(limit)
            
            return validated_data

        except Exception as e:
            log.error("data_loader.get_market_data.fail", extra={"extra": {"symbols": symbols, "error": repr(e)}})
            return {symbol: pd.DataFrame() for symbol in symbols}


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
