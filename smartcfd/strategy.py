import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import pandas as pd
import joblib

from .portfolio import PortfolioManager
from .data_loader import DataLoader, has_data_gaps
from .indicators import (
    atr, rsi, macd, bollinger_bands, adx,
    stochastic_oscillator, volume_profile, price_rate_of_change
)
from .regime_detector import MarketRegime
from .config import AppConfig
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

log = logging.getLogger(__name__)


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create a rich set of features for the model from historical data.
    This function must be identical to the one in `model_trainer.py`.
    """
    if df.empty:
        return pd.DataFrame()

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
    
    adx_df = adx(df['high'], df['low'], df['close'])
    features['feature_adx'] = adx_df['ADX_14']
    
    proc = price_rate_of_change(df['close'])
    features['feature_proc'] = proc

    bollinger = bollinger_bands(df['close'])
    features['feature_bband_mavg'] = bollinger['BBM_20_2.0']
    features['feature_bband_hband'] = bollinger['BBH_20_2.0']
    features['feature_bband_lband'] = bollinger['BBL_20_2.0']

    macd_df = macd(df['close'])
    features['feature_macd'] = macd_df['MACD_12_26_9']
    features['feature_macd_signal'] = macd_df['MACDs_12_26_9']
    features['feature_macd_diff'] = macd_df['MACDh_12_26_9']

    stoch = stochastic_oscillator(df['high'], df['low'], df['close'])
    features['feature_stoch_k'] = stoch['STOCHk_14_3_3']
    features['feature_stoch_d'] = stoch['STOCHd_14_3_3']

    # Time-based features
    features['feature_day_of_week'] = df.index.dayofweek
    features['feature_hour_of_day'] = df.index.hour
    features['feature_minute_of_hour'] = df.index.minute

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
    def __init__(self, model_path: str = "models/model.joblib", data_loader: DataLoader = None, config: AppConfig = None, trade_confidence_threshold: float = 0.75):
        self.model_path = model_path
        self.model = self.load_model(model_path)
        self.data_loader = data_loader or DataLoader()
        self.config = config
        self.trade_confidence_threshold = trade_confidence_threshold

    def load_model(self, model_path: str):
        if not Path(model_path).exists():
            log.error(f"inference_strategy.load_model.not_found path='{model_path}'")
            return None
        try:
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
        
        # If market_regimes is None, it's a data-gathering pass.
        if market_regimes is None:
            # If historical_data is not provided, fetch it.
            if historical_data is None:
                # We need enough data for regime detection AND feature creation.
                # Add a buffer to the minimum required points.
                limit = self.config.min_data_points + 50 
                historical_data = self.data_loader.get_market_data(
                    symbols=watch_list,
                    interval=self.config.trade_interval,
                    limit=limit
                )
            return [], historical_data

        # If we are in the action phase but no regimes were detected, exit early.
        if not market_regimes:
            log.warning("inference_strategy.evaluate.no_regimes_dict")
            # Return historical_data if it exists, otherwise an empty dict
            return [], historical_data or {}

        # If historical_data was passed, use it; otherwise, fetch it.
        if historical_data is None:
            limit = self.config.min_data_points + 50
            historical_data = self.data_loader.get_market_data(
                symbols=watch_list,
                interval=self.config.trade_interval,
                limit=limit
            )

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

                # Align columns with the model's expected features
                model_features = joblib.load('models/feature_names.joblib')
                features = features[model_features]

                prediction = self.model.predict(features.tail(1))
                probabilities = self.model.predict_proba(features.tail(1))[0]
                
                log.info(
                    f"inference_strategy.evaluate.predict_proba symbol={symbol} probabilities={probabilities.tolist()} prediction={int(prediction[0])}"
                )

                # New logic: Check probabilities for Buy (1) and Sell (2) signals
                buy_prob = probabilities[1]
                sell_prob = probabilities[2]
                
                decision = 'hold'
                action_prob = 0.0

                if buy_prob > self.trade_confidence_threshold:
                    decision = 'buy'
                    action_prob = buy_prob
                elif sell_prob > self.trade_confidence_threshold:
                    decision = 'sell'
                    action_prob = sell_prob

                log.info(
                    f"prediction for {symbol}: {prediction[0]}, decision: {decision}, "
                    f"buy_prob: {buy_prob:.4f}, sell_prob: {sell_prob:.4f}, "
                    f"threshold: {self.trade_confidence_threshold}, regime: {current_regime}"
                )

                if decision != 'hold':
                    actions.append({
                        "action": decision,
                        "symbol": symbol,
                        "confidence": action_prob
                    })

            except Exception:
                log.error("inference_strategy.evaluate.action_error", extra={"extra": {"symbol": symbol}}, exc_info=True)

        return actions, historical_data

    def map_prediction_to_action(self, prediction: int, symbol: str, regime: str) -> Dict[str, str]:
        """Maps a model's integer prediction to a trading action."""
        # This function is now effectively bypassed by the new logic in evaluate()
        # but we keep it for potential future use or different strategies.
        if prediction == 1:
            decision = "buy"
        elif prediction == 2:
            decision = "sell"
        else:
            decision = "hold"

        log.info(f"prediction for {symbol}: {prediction}, decision: {decision}, regime: {regime}")

        return {"action": decision, "symbol": symbol, "decision": decision}


def get_strategy_by_name(name: str, app_config: AppConfig) -> Strategy:
    """
    A simple factory to get a strategy instance by name.
    """
    if name == "dry_run":
        return DryRunStrategy()
    elif name == "inference":
        return InferenceStrategy(config=app_config)
    # Add other strategies here
    # elif name == "moving_average_crossover":
    #     return MovingAverageCrossoverStrategy()
    else:
        raise ValueError(f"Unknown strategy: {name}")
