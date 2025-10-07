from abc import ABC, abstractmethod
import logging
from typing import List, Dict, Any
from pathlib import Path
import joblib
import pandas as pd
from datetime import datetime, timedelta

from smartcfd.alpaca_client import AlpacaClient
from smartcfd.data_loader import DataLoader
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
        
        try:
            # 1. Fetch live market data for the symbol.
            data_loader = DataLoader(api_base=client.api_base)
            data = data_loader.get_market_data([self.symbol], "15m", limit=100)
            if data is None or data.empty:
                log.warning("strategy.inference.evaluate.no_data", extra={"extra": {"symbol": self.symbol}})
                return [{"action": "log", "symbol": self.symbol, "decision": "hold", "reason": "no_data"}]

            # 2. Calculate features from the data.
            features = calculate_indicators(data)
            if features.empty:
                log.warning("strategy.inference.evaluate.no_features", extra={"extra": {"symbol": self.symbol}})
                return [{"action": "log", "symbol": self.symbol, "decision": "hold", "reason": "feature_calculation_failed"}]

            # 3. Make a prediction using the model.
            latest_features = features.iloc[-1:]
            
            prediction = self.model.predict(latest_features)[0]
            
            # 4. Translate the prediction into an action.
            if prediction == 1:
                decision = "buy"
            elif prediction == -1:
                decision = "sell"
            else:
                decision = "hold"
            
            log.info("strategy.inference.evaluate.prediction", extra={"extra": {"symbol": self.symbol, "prediction": prediction, "decision": decision}})

            if decision in ["buy", "sell"]:
                return [{"action": "order", "symbol": self.symbol, "decision": decision}]
            else:
                return [{"action": "log", "symbol": self.symbol, "decision": "hold", "reason": "model_hold"}]
        
        except Exception as e:
            log.error("strategy.inference.evaluate.fail", extra={"extra": {"symbol": self.symbol, "error": repr(e)}})
            return [{"action": "log", "symbol": self.symbol, "decision": "hold", "reason": "evaluation_exception"}]


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
