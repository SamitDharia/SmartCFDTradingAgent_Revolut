import os
import pandas as pd
import requests
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

def _parse_interval(interval_str: str) -> TimeFrame:
    """Parses a string like '15m', '1h', '1d' into an Alpaca TimeFrame."""
    try:
        unit_map = {
            'm': TimeFrameUnit.Minute,
            'h': TimeFrameUnit.Hour,
            'd': TimeFrameUnit.Day,
        }
        amount = int(interval_str[:-1])
        unit_char = interval_str[-1].lower()
        unit = unit_map.get(unit_char)
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
