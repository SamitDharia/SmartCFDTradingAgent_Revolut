import logging
from typing import List, Dict, Any

from .strategy import Strategy
from .broker import Broker
from .risk import RiskManager

log = logging.getLogger(__name__)

class Trader:
    """
    The Trader class orchestrates the trading process.
    It uses a Strategy to get trading signals and a Broker to execute them.
    A RiskManager is used to size the orders.
    """

    def __init__(self, strategy: Strategy, broker: Broker, risk_manager: RiskManager):
        self.strategy = strategy
        self.broker = broker
        self.risk_manager = risk_manager

    def run(self):
        """
        Runs the trading loop.
        """
        log.info("trader.run.start")
        try:
            # The strategy's client is the broker's client
            actions = self.strategy.evaluate(self.broker.client)
            self.execute_actions(actions)
            log.info("trader.run.end")
        except Exception as e:
            log.error("trader.run.fail", extra={"extra": {"error": repr(e)}})

    def execute_actions(self, actions: List[Dict[str, Any]]):
        """
        Executes a list of actions received from the strategy.
        """
        if not actions:
            log.info("trader.execute_actions.no_actions")
            return

        for action in actions:
            log.info("trader.execute_actions.processing", extra={"extra": {"action": action}})
            action_type = action.get("action")

            if action_type == "log":
                log.info("trader.action.log", extra={"extra": action})
            
            elif action_type == "buy":
                self.execute_order(action)

            else:
                log.warning("trader.execute_actions.unknown_action", extra={"extra": {"action_type": action_type}})

    def execute_order(self, order_details: Dict[str, Any]):
        """
        Executes a single order action after consulting the risk manager.
        """
        try:
            symbol = order_details["symbol"]
            side = "buy" # Inferred from the action type

            # 1. Get order size from Risk Manager
            qty = self.risk_manager.calculate_order_qty(symbol, side)
            if qty == 0:
                log.info("trader.execute_order.zero_qty", extra={"extra": {"symbol": symbol, "side": side}})
                return

            # 2. Submit the order
            order_result = self.broker.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                order_type="market",
                time_in_force="gtc"
            )
            log.info("trader.execute_order.success", extra={"extra": {"order_result": order_result}})

        except Exception as e:
            log.error("trader.execute_order.fail", extra={"extra": {"error": repr(e), "order_details": order_details}})


