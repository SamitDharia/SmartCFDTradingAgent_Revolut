from abc import ABC, abstractmethod
import logging
from typing import List, Dict, Any
from smartcfd.alpaca_client import AlpacaClient

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

class StrategyHarness:
    """
    A harness for running and evaluating a trading strategy.
    """
    def __init__(self, client: AlpacaClient, strategy: Strategy):
        self.client = client
        self.strategy = strategy

    def run(self):
        """
        Run the strategy and log the proposed actions.
        In the future, this could be extended to execute orders.
        """
        log.info("harness.run.start", extra={"extra": {"strategy": self.strategy.__class__.__name__}})
        try:
            actions = self.strategy.evaluate(self.client)
            log.info("harness.run.actions", extra={"extra": {"actions": actions}})
            
            # Here you could add logic to execute the actions (e.g., post orders)
            for action in actions:
                if action.get("action") == "buy":
                    # client.post_order(...)
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
    # Add other strategies here
    # elif name == "moving_average_crossover":
    #     return MovingAverageCrossoverStrategy()
    else:
        raise ValueError(f"Unknown strategy: {name}")
