import logging
from typing import List, Dict, Any
import pandas as pd

from .strategy import Strategy
from .broker import Broker
from .risk import RiskManager
from .portfolio import PortfolioManager
from .regime_detector import RegimeDetector, MarketRegime

log = logging.getLogger(__name__)

class Trader:
    """
    The Trader class orchestrates the trading process.
    It uses a Strategy to get trading signals and a Broker to execute them.
    A RiskManager is used to size the orders.
    """

    def __init__(self, portfolio_manager: PortfolioManager, strategy: Strategy, risk_manager: RiskManager, app_config: Any):
        self.portfolio_manager = portfolio_manager
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.app_config = app_config
        self.regime_detector = RegimeDetector()
        # The broker client is now accessed via the portfolio manager
        self.broker = portfolio_manager.client

    def run(self):
        """
        Runs the trading loop.
        """
        watch_list = self.app_config.watch_list.split(',')
        interval = self.app_config.trade_interval
        log.info(
            "trader.run.start",
            extra={"extra": {"watch_list": watch_list, "interval": interval}},
        )
        try:
            # 1. Reconcile portfolio state with the broker
            self.portfolio_manager.reconcile()

            # 2. Check for global halt conditions (e.g., max drawdown)
            if self.risk_manager.check_for_halt(watch_list, interval):
                log.critical("trader.run.halted", extra={"extra": {"reason": self.risk_manager.halt_reason}})
                return

            # 3. Evaluate strategy to get actions and historical data
            log.info("trader.run.evaluating_strategy")
            actions, historical_data = self.strategy.evaluate(self.portfolio_manager, watch_list)

            # 4. Detect market regime for each symbol
            for symbol, data in historical_data.items():
                regime = self.regime_detector.detect_regime(data)
                log.info("trader.run.regime_detected", extra={"extra": {"symbol": symbol, "regime": regime.value}})
            
            # 5. Execute actions
            self.execute_actions(actions, historical_data)
            log.info("trader.run.end")
        except Exception:
            log.error("trader.run.fail", exc_info=True)

    def execute_actions(self, actions: List[Dict[str, Any]], historical_data: Dict[str, pd.DataFrame]):
        """
        Executes a list of actions received from the strategy, after risk checks.
        """
        if not actions:
            log.info("trader.execute_actions.no_actions")
            return

        log.info(
            "trader.execute_actions.processing_actions",
            extra={"extra": {"action_count": len(actions)}},
        )
        for action in actions:
            log.info("trader.execute_actions.processing", extra={"extra": {"action": action}})
            action_type = action.get("action")
            symbol = action.get("symbol")

            if action_type == "log":
                log.info("trader.action.log", extra={"extra": action})
            
            elif action_type in ("buy", "sell"):
                # Perform volatility check before executing a trade order
                if symbol and symbol in historical_data and self.risk_manager.is_volatility_too_high(historical_data[symbol], symbol):
                    log.warning("trader.execute_order.halted_volatility", 
                                extra={"extra": {"symbol": symbol, "reason": "Circuit breaker tripped due to high volatility."}})
                    continue # Skip this action

                self.execute_order(action)

            else:
                log.warning("trader.execute_actions.unknown_action", extra={"extra": {"action_type": action_type}})

    def execute_order(self, order_details: Dict[str, Any]):
        """
        Executes a single order action after consulting the risk manager for size.
        """
        try:
            symbol = order_details["symbol"]
            side = order_details["action"] # "buy" or "sell"

            # 1. Get order size from Risk Manager
            log.info(
                "trader.execute_order.calculating_qty",
                extra={"extra": {"symbol": symbol, "side": side}},
            )
            qty = self.risk_manager.calculate_order_qty(symbol, side)
            if qty <= 0:
                log.warning(
                    "trader.execute_order.zero_or_neg_qty",
                    extra={"extra": {"symbol": symbol, "side": side, "qty": qty}},
                )
                return

            # 2. Submit the order via the portfolio manager's client
            log.info(
                "trader.execute_order.submitting",
                extra={"extra": {"symbol": symbol, "side": side, "qty": qty}},
            )
            order_result = self.portfolio_manager.client.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                order_type="market",
                time_in_force="gtc"
            )
            log.info("trader.execute_order.success", extra={"extra": {"order_result": order_result}})

        except Exception:
            log.error(
                "trader.execute_order.fail",
                extra={"extra": {"order_details": order_details}},
                exc_info=True,
            )


