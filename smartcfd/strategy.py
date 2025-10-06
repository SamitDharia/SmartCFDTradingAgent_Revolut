from abc import ABC, abstractmethod
import logging
from typing import List, Dict, Any
from pathlib import Path
import joblib

from smartcfd.alpaca_client import AlpacaClient
from smartcfd.risk import RiskManager

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
    def __init__(self, symbol: str = "BTC/USD"):
        self.symbol = symbol
        self.model = None
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
        
        # Placeholder for fetching data and generating features
        log.info("strategy.inference.evaluate.start", extra={"extra": {"symbol": self.symbol}})
        
        # In a real implementation, this is where you would:
        # 1. Fetch live market data for the symbol.
        # 2. Generate the same features the model was trained on.
        # 3. Use self.model.predict() or self.model.predict_proba()
        # 4. Map the prediction to a decision (buy/sell/hold).
        
        # For now, we'll just log and return a hold decision.
        return [{"action": "log", "symbol": self.symbol, "decision": "hold", "reason": "inference_dry_run"}]


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
