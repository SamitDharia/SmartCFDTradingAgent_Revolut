import logging
import requests
from typing import Callable, Dict, Any

from smartcfd.alpaca import build_headers_from_env

log = logging.getLogger("trader")

# A simple strategy is just a function that takes a session and returns a decision
StrategyFunction = Callable[[requests.Session], Dict[str, Any]]

def example_strategy(session: requests.Session) -> Dict[str, Any]:
    """A placeholder strategy that does nothing."""
    log.info("strategy.example.run")
    # In the future, this would analyze data and return trade signals
    return {"action": "hold", "reason": "market is flat"}

class TradingSession:
    def __init__(self, api_base: str, timeout: float, strategy: StrategyFunction):
        self.api_base = api_base
        self.timeout = timeout
        self.strategy = strategy
        self.session = requests.Session()
        self.session.headers.update(build_headers_from_env())

    def is_market_open(self) -> bool:
        """Check if the market is currently open."""
        try:
            r = self.session.get(f"{self.api_base}/v2/clock", timeout=self.timeout)
            r.raise_for_status()
            data = r.json()
            is_open = data.get("is_open", False)
            log.info("trader.market_check", extra={"extra": {"is_open": is_open, "next_open": data.get("next_open"), "next_close": data.get("next_close")}})
            return is_open
        except requests.RequestException as e:
            log.error("trader.market_check.fail", extra={"extra": {"error": repr(e)}})
            return False

    def run_strategy_if_market_open(self):
        """Executes the trading strategy if the market is open."""
        if self.is_market_open():
            log.info("trader.run.market_open")
            try:
                decision = self.strategy(self.session)
                log.info("trader.strategy.decision", extra={"extra": decision})
            except Exception as e:
                log.error("trader.strategy.fail", extra={"extra": {"error": repr(e)}})
        else:
            log.info("trader.run.market_closed")

