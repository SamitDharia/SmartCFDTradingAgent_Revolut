from abc import ABC, abstractmethod
import logging
from typing import List, Dict, Any
from pathlib import Path
import joblib
import pandas as pd
from datetime import datetime, timedelta

from smartcfd.alpaca_client import AlpacaClient
from smartcfd.data_loader import fetch_data
from alpaca.data.timeframe import TimeFrame
from .indicators import create_features as calculate_indicators

log = logging.getLogger("strategy")

class Strategy(ABC):
    """
    Abstract base class for a trading strategy.
    """
    @abstractmethod
    def evaluate(self, client: AlpacaClient) -> List[Dict[str, Any]]:
        """
        Evaluate the strategy and return a list of proposed actions (e.g., orders).
        
        :param client: An instance of AlpacaClient to interact with the market.
        :return: A list of dictionaries, each representing a proposed action.
        """
        pass

class DryRunStrategy(Strategy):
    """
    A simple strategy that logs the account information and proposes no actions.
    This is useful for verifying that the strategy evaluation pipeline is working.
    """
    def evaluate(self, client: AlpacaClient) -> List[Dict[str, Any]]:
        log.info("strategy.dry_run.evaluate")
        try:
            symbols_to_watch = ["BTC/USD"]
            log.info("strategy.dry_run.watching", extra={"extra": {"symbols": symbols_to_watch}})
            
            return [
                {"action": "log", "symbol": symbol, "decision": "hold", "reason": "dry_run"}
                for symbol in symbols_to_watch
            ]
        except Exception as e:
            log.error("strategy.dry_run.fail", extra={"extra": {"error": repr(e)}})
            return []

class InferenceStrategy(Strategy):
    """
    A strategy that uses a trained model to make trading decisions.
    """
    def __init__(self, symbol: str = "BTC/USD", model_path: str = "models/model.joblib"):
        self.symbol = symbol
        self.model_path = Path(model_path)
        self.model = self.load_model()

    def load_model(self) -> object | None:
        """Loads the model from the specified path."""
        if self.model_path and self.model_path.exists():
            try:
                model = joblib.load(self.model_path)
                log.info(f"strategy.inference.model_loaded", extra={"extra": {"model_path": str(self.model_path)}})
                return model
            except Exception as e:
                log.error(f"strategy.inference.model_load_fail", extra={"extra": {"error": repr(e)}})
                return None
        else:
            log.warning(f"strategy.inference.no_model_found", extra={"extra": {"path": str(self.model_path)}})
            return None

    def evaluate(self, client: AlpacaClient) -> List[Dict[str, Any]]:
        if not self.model:
            log.warning("strategy.inference.evaluate.no_model", extra={"extra": {"reason": "Model not loaded."}})
            return [{"action": "log", "symbol": self.symbol, "decision": "hold", "reason": "no_model"}]
        
        log.info("strategy.inference.evaluate.start", extra={"extra": {"symbol": self.symbol}})
        
        # 1. Fetch live market data for the symbol.
        # We need enough data to calculate the indicators. Let's fetch data for the last 100 days.
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=100)
        
        try:
            df = fetch_data(self.symbol, TimeFrame.Hour, start_date.isoformat(), end_date.isoformat())
        except Exception as e:
            log.error("strategy.inference.evaluate.data_fetch_fail", extra={"extra": {"error": repr(e)}})
            return [{"action": "log", "symbol": self.symbol, "decision": "hold", "reason": "data_fetch_fail"}]

        if df.empty:
            log.warning("strategy.inference.evaluate.no_data", extra={"extra": {"symbol": self.symbol}})
            return [{"action": "log", "symbol": self.symbol, "decision": "hold", "reason": "no_data"}]

        # The Alpaca API might return a multi-index (symbol, timestamp).
        # We need to set the timestamp as the primary index for feature calculation.
        if isinstance(df.index, pd.MultiIndex):
            df.index = df.index.get_level_values('timestamp')

        # 2. Generate the same features the model was trained on.
        df_features = calculate_indicators(df)
        
        # Get the latest features
        latest_features = df_features.iloc[-1:]
        
        # Ensure the feature names match the model's expected input
        model_features = self.model.feature_names_in_
        latest_features = latest_features[model_features]

        # 3. Use self.model.predict() or self.model.predict_proba()
        try:
            prediction = self.model.predict(latest_features)
            prediction_proba = self.model.predict_proba(latest_features)
            
            score = prediction_proba[0][1] # Probability of the 'up' class
            
            # 4. Map the prediction to a decision (buy/sell/hold).
            decision = "hold"
            if prediction[0] == 1 and score > 0.55: # Example threshold
                decision = "buy"
            
            log.info("strategy.inference.evaluate.result", extra={"extra": {
                "symbol": self.symbol,
                "decision": decision,
                "score": score,
                "prediction": int(prediction[0])
            }})

            if decision == "buy":
                return [{"action": "buy", "symbol": self.symbol, "reason": "inference", "score": score}]
            else:
                return [{"action": "log", "symbol": self.symbol, "decision": "hold", "reason": "inference_hold", "score": score}]

        except Exception as e:
            log.error("strategy.inference.evaluate.fail", extra={"extra": {"error": repr(e)}})
            return [{"action": "log", "symbol": self.symbol, "decision": "hold", "reason": "evaluation_error"}]


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
