import os
import pandas as pd
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from smartcfd.config import load_config

def get_crypto_data_client() -> CryptoHistoricalDataClient:
    """Returns an Alpaca crypto data client."""
    return CryptoHistoricalDataClient()

def fetch_data(symbol: str, timeframe: TimeFrame, start: str, end: str) -> pd.DataFrame:
    """
    Fetches historical crypto data from Alpaca.
    """
    client = get_crypto_data_client()
    request = CryptoBarsRequest(
        symbol_or_symbols=[symbol],
        timeframe=timeframe,
        start=start,
        end=end
    )
    bars = client.get_crypto_bars(request)
    return bars.df
