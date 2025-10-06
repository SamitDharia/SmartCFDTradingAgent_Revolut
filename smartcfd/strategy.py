from abc import ABC, abstractmethod
import logging
from typing import List, Dict, Any
from pathlib import Path
import joblib
import pandas as pd
from datetime import datetime, timedelta

from smartcfd.alpaca_client import AlpacaClient
from smartcfd.risk import RiskManager
from SmartCFDTradingAgent.indicators import create_features as calculate_indicators

log = logging.getLogger("strategy")

STORAGE_PATH = Path(__file__).resolve().parents[1] / "SmartCFDTradingAgent" / "storage"

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
            # Example of using the client to get account info
            # Note: This endpoint doesn't exist, it's for demonstration purposes.
            # A real strategy would fetch market data, positions, etc.
            # account_info = client.session.get(f"{client.api_base}/v2/account").json()
            # log.info("strategy.dry_run.account_info", extra={"extra": {"account": account_info}})
            
            # In a real scenario, you might analyze market data for a list of symbols
            symbols_to_watch = ["AAPL", "GOOG", "MSFT"]
            log.info("strategy.dry_run.watching", extra={"extra": {"symbols": symbols_to_watch}})
            
            # This strategy will not propose any trades
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
    def __init__(self, symbol: str = "BTC/USD", model: object = None):
        self.symbol = symbol
        self.model = model
        self.model_path = None
        
        if self.model is None:
            self.model_path = self._find_latest_model()
            if self.model_path:
                self.load_model()

    def _find_latest_model(self) -> Path | None:
        """Finds the latest model file for the given symbol."""
        model_files = list(STORAGE_PATH.glob(f"model__{self.symbol.replace('/', '')}__*.joblib"))
        if not model_files:
            log.warning(f"strategy.inference.no_model_found", extra={"extra": {"symbol": self.symbol}})
            return None
        latest_model = max(model_files, key=lambda p: p.stat().st_mtime)
        log.info(f"strategy.inference.found_model", extra={"extra": {"model_path": str(latest_model)}})
        return latest_model

    def load_model(self):
        """Loads the model from the specified path."""
        if self.model_path and self.model_path.exists():
            try:
                self.model = joblib.load(self.model_path)
                log.info(f"strategy.inference.model_loaded", extra={"extra": {"model_path": str(self.model_path)}})
            except Exception as e:
                log.error(f"strategy.inference.model_load_fail", extra={"extra": {"error": repr(e)}})
                self.model = None
        else:
            log.warning("strategy.inference.model_path_not_found")

    def evaluate(self, client: AlpacaClient) -> List[Dict[str, Any]]:
        if not self.model:
            log.warning("strategy.inference.evaluate.no_model", extra={"extra": {"reason": "Model not loaded."}})
            return [{"action": "log", "symbol": self.symbol, "decision": "hold", "reason": "no_model"}]
        
        log.info("strategy.inference.evaluate.start", extra={"extra": {"symbol": self.symbol}})
        
        # 1. Fetch live market data for the symbol.
        # We need enough data to calculate the indicators. Let's fetch 100 days of daily data.
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=100)
        
        bars = client.get_bars(self.symbol, "1D", start_date.isoformat(), end_date.isoformat())
        if not bars:
            log.warning("strategy.inference.evaluate.no_data", extra={"extra": {"symbol": self.symbol}})
            return [{"action": "log", "symbol": self.symbol, "decision": "hold", "reason": "no_data"}]

        df = pd.DataFrame(bars)
        df['time'] = pd.to_datetime(df['t'])
        df = df.set_index('time')

        # 2. Generate the same features the model was trained on.
        df_features = calculate_indicators(df)
        
        # Get the latest features
        latest_features = df_features.iloc[-1:]
        
        # Ensure the feature names match the model's expected input
        if hasattr(self.model, 'feature_names_in_'):
            model_features = self.model.feature_names_in_
        elif hasattr(self.model, 'get_booster'): # Fallback for raw XGBoost models
            model_features = self.model.get_booster().feature_names
        else:
            raise AttributeError("Could not determine model's feature names.")
        
        latest_features = latest_features[model_features]

        # 3. Use self.model.predict() or self.model.predict_proba()
        try:
            prediction = self.model.predict(latest_features)
            prediction_proba = self.model.predict_proba(latest_features)
            
            score = prediction_proba[0][1] # Probability of the 'up' class
            
            # 4. Map the prediction to a decision (buy/sell/hold).
            decision = "hold"
            if prediction[0] == 1 and score > 0.6: # Example threshold
                decision = "buy"
            elif prediction[0] == 0 and score < 0.4: # Example threshold
                decision = "sell"

            log.info("strategy.inference.evaluate.result", extra={"extra": {
                "symbol": self.symbol,
                "decision": decision,
                "score": score,
                "prediction": int(prediction[0])
            }})

            return [{"action": "log", "symbol": self.symbol, "decision": decision, "reason": "inference"}]

        except Exception as e:
            log.error("strategy.inference.evaluate.fail", extra={"extra": {"error": repr(e)}})
            return [{"action": "log", "symbol": self.symbol, "decision": "hold", "reason": "evaluation_error"}]


class StrategyHarness:
    """
    A harness for running and evaluating a trading strategy, with risk management.
    """
    def __init__(self, client: AlpacaClient, strategy: Strategy, risk_manager: RiskManager):
        self.client = client
        self.strategy = strategy
        self.risk_manager = risk_manager

    def run(self):
        """
        Run the strategy and log the proposed actions, after passing them through the risk manager.
        """
        log.info("harness.run.start", extra={"extra": {"strategy": self.strategy.__class__.__name__}})
        try:
            # 1. Check for global halts (e.g., max drawdown)
            if self.risk_manager.check_for_halt():
                log.warning("harness.run.halted", extra={"extra": {"reason": "Risk manager initiated a trading halt."}})
                return

            # 2. Evaluate the strategy to get proposed actions
            actions = self.strategy.evaluate(self.client)
            log.info("harness.run.proposed_actions", extra={"extra": {"actions": actions}})

            # 3. Filter actions through the risk manager
            approved_actions = self.risk_manager.filter_actions(actions)
            log.info("harness.run.approved_actions", extra={"extra": {"actions": approved_actions}})
            
            # 4. Execute the approved actions
            for action in approved_actions:
                if action.get("action") == "buy":
                    # In a real implementation, you would post the order
                    # self.client.post_order(...)
                    log.info("harness.run.executing_buy", extra={"extra": {"order_details": action.get("order_details")}})
                    pass
        except Exception as e:
            log.error("harness.run.fail", extra={"extra": {"error": repr(e)}})
        finally:
            log.info("harness.run.end")

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
