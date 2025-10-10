import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import pandas as pd
import joblib
import os

from .portfolio import PortfolioManager
from .data_loader import DataLoader, has_data_gaps
from .indicators import (
    atr, rsi, macd, bollinger_bands, adx,
    stochastic_oscillator, volume_profile, price_rate_of_change
)
from .regime_detector import MarketRegime
from .config import AppConfig
from .broker import Broker
from alpaca_trade_api.rest import TimeFrame, TimeFrameUnit

log = logging.getLogger(__name__)


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create a rich set of features for the model from historical data.
    This function must be identical to the one in `model_trainer.py`.
    """
    if df.empty:
        return pd.DataFrame()

    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, utc=True)

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
    # Default names from the 'ta' library are 'STOCHk_14_3_3' and 'STOCHd_14_3_3'
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

    # Volume Profile (simple version)
    vp = volume_profile(df['close'], df['volume'])
    features = features.join(vp.add_prefix('feature_vp_'))

    # Price Rate of Change
    features['feature_proc'] = price_rate_of_change(df['close'])

    return features


class Strategy(ABC):
    """
    Abstract base class for all trading strategies.
    Defines the interface that the Trader class will use.
    """
    def __init__(self, app_config: AppConfig, broker: Broker):
        self.app_config = app_config
        self.broker = broker
        self.data_loader = DataLoader(broker.api_key, broker.secret_key, broker.base_url)

    def get_historical_data(self, symbols: List[str]) -> Dict[str, pd.DataFrame]:
        """Fetches historical data for the given symbols."""
        return self.data_loader.get_market_data(
            symbols=symbols,
            interval=self.app_config.trade_interval,
            limit=self.app_config.min_data_points
        )

    @abstractmethod
    def evaluate(self, symbol: str, regime: str, historical_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        The core of the strategy.
        Analyzes historical data and market regime to generate a trading signal.
        A signal is a dictionary containing at least 'side' (buy/sell) and 'confidence'.
        """
        pass


class InferenceStrategy(Strategy):
    """
    A strategy that uses a pre-trained machine learning model to make trading decisions.
    """
    def __init__(self, app_config: AppConfig, broker: Broker):
        super().__init__(app_config, broker)
        self.model_path = Path(os.getenv("MODEL_PATH", "models/model.joblib"))
        self.feature_names_path = Path(os.getenv("FEATURE_NAMES_PATH", "models/feature_names.joblib"))
        
        if not self.model_path.exists() or not self.feature_names_path.exists():
            log.error("inference.strategy.init.fail", extra={"extra": {"reason": "Model or feature names file not found."}})
            raise FileNotFoundError("Model or feature names file not found.")
            
        self.model = joblib.load(self.model_path)
        self.feature_names = joblib.load(self.feature_names_path)
        log.info("inference.strategy.init.success")

    def evaluate(self, symbol: str, regime: str, historical_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Generates a trading signal using the loaded ML model.
        """
        if historical_data.empty or len(historical_data) < self.app_config.min_data_points:
            log.warning("inference.generate_signal.no_data", extra={"extra": {"symbol": symbol, "data_points": len(historical_data)}})
            return None

        # 1. Feature Engineering
        features = create_features(historical_data)
        if features.empty:
            log.warning("inference.generate_signal.no_features", extra={"extra": {"symbol": symbol}})
            return None

        # Align features with the model's expected input
        latest_features = features.iloc[-1:]
        
        # Ensure all required feature names are present
        missing_features = set(self.feature_names) - set(latest_features.columns)
        if missing_features:
            log.error(f"Missing features required by model: {missing_features}")
            return None
            
        latest_features = latest_features[self.feature_names]

        # 2. Prediction
        try:
            prediction = self.model.predict(latest_features)[0]
            confidence = self.model.predict_proba(latest_features)[0].max()
            log.info("inference.predict.details", extra={"symbol": symbol, "prediction": prediction, "confidence": confidence, "features": latest_features.to_dict('records')[0]})
        except Exception as e:
            log.error("inference.predict.fail", extra={"symbol": symbol, "error": str(e)})
            return None

        # 3. Signal Generation
        action = None
        # The model was trained with labels: 0=Hold, 1=Buy, 2=Sell
        if confidence >= self.app_config.min_confidence:
            if prediction == '1':
                action = {'side': 'buy', 'confidence': confidence}
            elif prediction == '2':
                action = {'side': 'sell', 'confidence': confidence}

        if action:
            log.info(
                "inference.generate_signal.success",
                extra={
                    "symbol": symbol,
                    "side": action['side'],
                    "confidence": action['confidence'],
                    "regime": regime,
                }
            )
            return action

        log.info(
            "inference.generate_signal.hold",
            extra={
                "symbol": symbol,
                "prediction": prediction,
                "confidence": confidence,
                "regime": regime,
            }
        )
        return None


def get_strategy_by_name(strategy_name: str, app_config: AppConfig, broker: Broker) -> "Strategy":
    """Factory function to get a strategy instance by its name."""
    if strategy_name == "inference":
        return InferenceStrategy(app_config, broker)
    # Add other strategies here as they are implemented
    # e.g., elif strategy_name == "some_other_strategy":
    #          return SomeOtherStrategy(app_config, broker)
    else:
        raise ValueError(f"Unknown strategy: {strategy_name}")


class TrendFollowingStrategy(Strategy):
    """
    A classic trend-following strategy based on moving average crossovers.
    This is a simple example and not the primary strategy of the bot.
    """
    def __init__(self, app_config: AppConfig, broker: Broker, short_window: int = 40, long_window: int = 100):
        super().__init__(app_config, broker)
        self.short_window = short_window
        self.long_window = long_window

    def generate_signal(self, symbol: str, regime: str, historical_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        if historical_data.empty:
            return None

        short_mavg = historical_data['close'].rolling(window=self.short_window, min_periods=1).mean()
        long_mavg = historical_data['close'].rolling(window=self.long_window, min_periods=1).mean()

        # Crossover signals
        if short_mavg.iloc[-1] > long_mavg.iloc[-1] and short_mavg.iloc[-2] <= long_mavg.iloc[-2]:
            return {"side": "buy", "confidence": 1.0}  # High confidence on crossover
        elif short_mavg.iloc[-1] < long_mavg.iloc[-1] and short_mavg.iloc[-2] >= long_mavg.iloc[-2]:
            return {"side": "sell", "confidence": 1.0}
        else:
            return None

class MeanReversionStrategy(Strategy):
    """
    A mean-reversion strategy using Bollinger Bands.
    This is a simple example.
    """
    def __init__(self, app_config: AppConfig, broker: Broker, window: int = 20, std_dev: int = 2):
        super().__init__(app_config, broker)
        self.window = window
        self.std_dev = std_dev

    def generate_signal(self, symbol: str, regime: str, historical_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        if historical_data.empty:
            return None

        upper_band, lower_band = bollinger_bands(historical_data['close'], window=self.window, std_dev=self.std_dev)

        # Signals
        if historical_data['close'].iloc[-1] < lower_band.iloc[-1]:
            return {"side": "buy", "confidence": 0.8} # Confidence can be tuned
        elif historical_data['close'].iloc[-1] > upper_band.iloc[-1]:
            return {"side": "sell", "confidence": 0.8}
        else:
            return None

class PairsTradingStrategy(Strategy):
    """
    A pairs trading strategy that looks for deviations in the price ratio of two correlated assets.
    This is a more complex example and requires a different data loading and analysis approach.
    """
    def __init__(self, app_config: AppConfig, broker: Broker, pair: Tuple[str, str], window: int = 30, threshold: float = 2.0):
        super().__init__(app_config, broker)
        self.pair = pair
        self.window = window
        self.threshold = threshold

    def generate_signal(self, symbol: str, regime: str, historical_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        # This strategy needs data for both assets in the pair.
        # The `historical_data` passed in is only for one symbol.
        # A real implementation would need to fetch data for the other symbol.
        
        # For demonstration, we'll assume `symbol` is the first asset in the pair
        # and we have a way to get the other asset's data.
        
        # Placeholder logic
        log.warning("PairsTradingStrategy is not fully implemented and is for demonstration purposes only.")
        return None

    def _calculate_spread(self, data1: pd.DataFrame, data2: pd.DataFrame) -> pd.Series:
        """Calculate the price ratio or spread between two assets."""
        # Ensure data is aligned by timestamp
        merged_data = pd.merge(data1['close'], data2['close'], left_index=True, right_index=True, suffixes=('_1', '_2'))
        spread = merged_data['close_1'] / merged_data['close_2']
        return spread

    def _calculate_zscore(self, spread: pd.Series) -> pd.Series:
        """Calculate the z-score of the spread."""
        mean = spread.rolling(window=self.window).mean()
        std = spread.rolling(window=self.window).std()
        zscore = (spread - mean) / std
        return zscore


class ArbitrageStrategy(Strategy):
    """
    An arbitrage strategy that looks for price discrepancies across different exchanges.
    This is highly complex and requires real-time data from multiple venues.
    """
    def __init__(self, app_config: AppConfig, broker: Broker, exchanges: List[str]):
        super().__init__(app_config, broker)
        self.exchanges = exchanges

    def generate_signal(self, symbol: str, regime: str, historical_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        # Placeholder logic
        log.warning("ArbitrageStrategy is not implemented and is for demonstration purposes only.")
        return None


class HighFrequencyStrategy(Strategy):
    """
    A high-frequency trading (HFT) strategy that operates on tick-level data.
    This requires a very low-latency setup and is beyond the scope of this bot.
    """
    def __init__(self, app_config: AppConfig, broker: Broker):
        super().__init__(app_config, broker)

    def generate_signal(self, symbol: str, regime: str, historical_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        # Placeholder logic
        log.warning("HighFrequencyStrategy is not implemented and is for demonstration purposes only.")
        return None


class SentimentAnalysisStrategy(Strategy):
    """
    A strategy that uses sentiment from news, social media, etc., to make trading decisions.
    Requires a data pipeline for sentiment analysis.
    """
    def __init__(self, app_config: AppConfig, broker: Broker, sentiment_source: str):
        super().__init__(app_config, broker)
        self.sentiment_source = sentiment_source

    def generate_signal(self, symbol: str, regime: str, historical_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        # Placeholder logic
        log.warning("SentimentAnalysisStrategy is not implemented and is for demonstration purposes only.")
        return None


class VolatilityBreakoutStrategy(Strategy):
    """
    A strategy that enters a trade when the price breaks out of a defined range (e.g., a Donchian Channel).
    """
    def __init__(self, app_config: AppConfig, broker: Broker, breakout_window: int = 20):
        super().__init__(app_config, broker)
        self.breakout_window = breakout_window

    def generate_signal(self, symbol: str, regime: str, historical_data: pd.DataFrame) -> Optional[Dict[str, Any]]:
        if historical_data.empty:
            return None

        highs = historical_data['high'].rolling(window=self.breakout_window).max()
        lows = historical_data['low'].rolling(window=self.breakout_window).min()

        current_price = historical_data['close'].iloc[-1]

        if current_price > highs.iloc[-2]: # Breakout above the previous period's high
            return {"side": "buy", "confidence": 0.9}
        elif current_price < lows.iloc[-2]: # Breakdown below the previous period's low
            return {"side": "sell", "confidence": 0.9}
        else:
            return None
