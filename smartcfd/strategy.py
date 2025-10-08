import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import pandas as pd
import joblib

from .portfolio import PortfolioManager
from .data_loader import DataLoader, has_data_gaps, has_zero_volume_anomaly
from .indicators import atr, rsi, macd, bollinger_bands, adx
from .regime_detector import MarketRegime
from .config import AppConfig, load_config
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

log = logging.getLogger(__name__)


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create features for the model from historical data.
    """
    if df.empty:
        return pd.DataFrame()

    # Ensure columns are lowercase for consistency
    df.columns = [x.lower() for x in df.columns]

    # Basic features
    features = pd.DataFrame(index=df.index)
    features['returns'] = df['close'].pct_change()

    # Technical Indicators
    features['rsi'] = rsi(df['close'])
    macd_df = macd(df['close'])
    features['macd'] = macd_df['MACD_12_26_9']
    features['macdsignal'] = macd_df['MACDs_12_26_9']
    
    bollinger = bollinger_bands(df['close'])
    features['bollinger_mavg'] = bollinger['BBM_20_2.0']
    features['bollinger_hband'] = bollinger['BBH_20_2.0']
    features['bollinger_lband'] = bollinger['BBL_20_2.0']

    adx_df = adx(df['high'], df['low'], df['close'])
    features['adx'] = adx_df['ADX_14']

    # Lagged features
    for lag in [1, 2, 3, 5, 10]:
        features[f'returns_lag_{lag}'] = features['returns'].shift(lag)
        features[f'rsi_lag_{lag}'] = features['rsi'].shift(lag)

    return features.dropna()


class Strategy(ABC):
    """
    Abstract base class for a trading strategy.
    Defines the interface for evaluating market data and generating trading signals.
    """

    @abstractmethod
    def evaluate(
        self,
        portfolio: PortfolioManager,
        watch_list: List[str],
        market_regimes: Optional[Dict[str, MarketRegime]] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, pd.DataFrame]]:
        """
        Evaluates the strategy for a list of symbols.

        Args:
            portfolio: The current portfolio state.
            watch_list: The list of symbols to evaluate.
            market_regimes: Optional dictionary of market regimes for each symbol.
                            If None, the strategy should operate in a data-gathering mode.

        Returns:
            A tuple containing:
            - A list of action dictionaries (e.g., {'symbol': 'BTC/USD', 'action': 'buy'}).
            - A dictionary of historical data for each symbol.
        """
        pass


class DryRunStrategy(Strategy):
    """
    A simple strategy for dry-running the system.
    It only logs the data it would have processed.
    """
    def __init__(self):
        self.data_loader = DataLoader()

    def evaluate(
        self,
        portfolio: PortfolioManager,
        watch_list: List[str],
        market_regimes: Optional[Dict[str, MarketRegime]] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, pd.DataFrame]]:
        log.info("dry_run_strategy.evaluate", extra={"extra": {"watch_list": watch_list, "market_regimes": market_regimes}})
        historical_data = {symbol: self.data_loader.get_market_data([symbol]) for symbol in watch_list}
        # Dry run doesn't produce actions
        return [], historical_data


class InferenceStrategy(Strategy):
    """
    A strategy that uses a trained model to make trading decisions.
    """
    def __init__(self, model_path: str = "models/model.joblib", data_loader: DataLoader = None, config: AppConfig = None):
        self.model_path = model_path
        self.model = self.load_model(model_path)
        self.data_loader = data_loader or DataLoader()
        self.config = config or load_config()

    def load_model(self, model_path: str):
        if not Path(model_path).exists():
            log.error(f"inference_strategy.load_model.not_found path='{model_path}'")
            return None
        try:
            log.info(f"inference_strategy.load_model.start path='{model_path}'")
            model = joblib.load(model_path)
            log.info("inference_strategy.load_model.success")
            return model
        except Exception:
            log.error("inference_strategy.load_model.fail", exc_info=True)
            return None

    def evaluate(
        self,
        portfolio: PortfolioManager,
        watch_list: List[str],
        market_regimes: Optional[Dict[str, MarketRegime]] = None,
        historical_data: Optional[Dict[str, pd.DataFrame]] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, pd.DataFrame]]:
        actions = []
        
        # Initialize historical_data if not provided
        if historical_data is None:
            historical_data = {}

        # If market regimes are NOT provided, this is the first pass for data loading.
        if not market_regimes:
            # First pass: load data for all symbols
            for symbol in watch_list:
                try:
                    # Fetch data with interval and a limit suitable for feature creation
                    data_dict = self.data_loader.get_market_data(
                        symbols=[symbol],
                        interval=self.config.trade_interval,
                        limit=200  # A reasonable lookback for feature calculation
                    )
                    if data_dict and symbol in data_dict:
                        data = data_dict[symbol]
                        if data is not None and not data.empty:
                            historical_data[symbol] = data
                    else:
                        log.warning("inference_strategy.evaluate.no_data_in_dict", extra={"extra": {"symbol": symbol}})
                except Exception:
                    log.error("inference_strategy.evaluate.data_load_error", extra={"extra": {"symbol": symbol}}, exc_info=True)
            
            # This was a data-gathering pass. Return the data.
            return [], historical_data

        # If we are here, it's the second pass (market_regimes is not None).
        # The historical_data from the first pass is used to generate actions.
        for symbol in watch_list:
            if symbol not in historical_data or historical_data[symbol].empty:
                log.warning("inference_strategy.evaluate.no_data", extra={"extra": {"symbol": symbol}})
                continue

            # --- Prediction ---
            try:
                current_regime = market_regimes.get(symbol)
                if not current_regime:
                    log.warning("inference_strategy.evaluate.no_regime", extra={"extra": {"symbol": symbol}})
                    continue

                features = create_features(historical_data[symbol])
                
                # Ensure we have data to predict on
                if features.empty:
                    log.warning("inference_strategy.evaluate.no_features", extra={"extra": {"symbol": symbol}})
                    continue

                prediction = self.model.predict(features.tail(1))
                action = self.map_prediction_to_action(prediction[0], symbol, current_regime)
                actions.append(action)

            except Exception:
                log.error("inference_strategy.evaluate.action_error", extra={"extra": {"symbol": symbol}}, exc_info=True)

        return actions, historical_data

    def map_prediction_to_action(self, prediction: int, symbol: str, regime: str) -> Dict[str, str]:
        """Maps a model's integer prediction to a trading action."""
        if prediction == 1:
            decision = "buy"
        elif prediction == 2:
            decision = "sell"
        else:
            decision = "hold"
        return {"action": decision, "symbol": symbol, "decision": decision}


def get_strategy_by_name(name: str) -> Strategy:
    """
    A simple factory to get a strategy instance by name.
    """
    if name == "dry_run":
        return DryRunStrategy()
    elif name == "inference":
        return InferenceStrategy()
    # Add other strategies here
    # elif name == "moving_average_crossover":
    #     return MovingAverageCrossoverStrategy()
    else:
        raise ValueError(f"Unknown strategy: {name}")
