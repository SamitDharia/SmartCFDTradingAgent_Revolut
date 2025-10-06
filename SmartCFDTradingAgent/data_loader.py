import os
import logging
from pathlib import Path
from datetime import datetime

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

log = logging.getLogger(__name__)

def get_data_client() -> StockHistoricalDataClient:
    """Initializes and returns an Alpaca historical data client."""
    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")
    if not api_key or not api_secret:
        raise ValueError("Alpaca API keys (APCA_API_KEY_ID, APCA_API_SECRET_KEY) are not set in environment.")
    return StockHistoricalDataClient(api_key, api_secret)

def fetch_and_cache_data(
    symbols: list[str],
    start_date: str,
    end_date: str,
    cache_dir: str = "storage/datasets",
    timeframe: TimeFrame = TimeFrame.Minute,
) -> Path:
    """
    Fetches historical stock data from Alpaca and saves it to a Parquet file.

    Args:
        symbols: A list of stock symbols to fetch.
        start_date: The start date in YYYY-MM-DD format.
        end_date: The end date in YYYY-MM-DD format.
        cache_dir: The directory to save the cache file in.
        timeframe: The timeframe for the bars (e.g., TimeFrame.Minute).

    Returns:
        The path to the cached Parquet file, or None if fetching fails.
    """
    log.info(f"Starting data fetch for {len(symbols)} symbols from {start_date} to {end_date}.")
    
    # Ensure cache directory exists
    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    
    # Generate a filename based on the request parameters
    symbols_str = "_".join(sorted(symbols))
    filename = f"{start_date}_{end_date}_{symbols_str}_{timeframe.value.replace(' ', '')}.parquet"
    output_file = cache_path / filename
    
    if output_file.exists():
        log.info(f"Data already cached at {output_file}. Skipping fetch.")
        return output_file

    client = get_data_client()
    
    request_params = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=timeframe,
        start=datetime.fromisoformat(start_date),
        end=datetime.fromisoformat(end_date)
    )
    
    try:
        bars = client.get_stock_bars(request_params)
        df = bars.df
        
        if df.empty:
            log.warning("No data returned from Alpaca for the given parameters.")
            return None

        # Reset index to have 'symbol' and 'timestamp' as columns
        df = df.reset_index()

        log.info(f"Fetched {len(df)} total bars. Saving to {output_file}...")
        df.to_parquet(output_file, index=False)
        log.info("Successfully saved data to cache.")
        
        return output_file

    except Exception as e:
        log.error(f"Failed to fetch or cache data: {e}", exc_info=True)
        return None



