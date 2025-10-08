import logging
from typing import List, Dict, Any, Optional
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

            # 2. First Pass: Evaluate strategy to get historical data for regime detection and risk checks
            log.info("trader.run.evaluating_strategy_data_pass")
            actions, historical_data = self.strategy.evaluate(
                self.portfolio_manager, 
                watch_list,
                market_regimes=None # Pass None to signal data gathering pass
            )

            # If the initial data load failed completely, historical_data might be empty.
            # In this case, we should not proceed.
            if not historical_data:
                log.warning("trader.run.no_data_from_strategy")
                return

            # 3. Check for global halt conditions (e.g., max drawdown, high volatility)
            if self.risk_manager.check_for_halt(historical_data, interval):
                log.critical("trader.run.halted", extra={"extra": {"reason": self.risk_manager.halt_reason}})
                return

            # 4. Detect market regime for each symbol
            market_regimes = {}
            for symbol, data in historical_data.items():
                if not data.empty:
                    regime = self.regime_detector.detect_regime(data)
                    market_regimes[symbol] = regime
                    log.info("trader.run.regime_detected", extra={"extra": {"symbol": symbol, "regime": regime.value}})

            # 5. Second Pass: Re-evaluate strategy with regime context to get final actions
            log.info("trader.run.evaluating_strategy_with_regime")
            actions, _ = self.strategy.evaluate( # We already have the data
                self.portfolio_manager, 
                watch_list, 
                market_regimes,
                historical_data=historical_data # Pass the data from the first run
            )

            # 6. Execute actions
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

                self.execute_order(action, historical_data.get(symbol))

            else:
                log.warning("trader.execute_actions.unknown_action", extra={"extra": {"action_type": action_type}})

    def execute_order(self, order_details: Dict[str, Any], historical_data: Optional[pd.DataFrame]):
        """
        Executes a single order action, handling long, short, and closing logic.
        """
        try:
            symbol = order_details["symbol"]
            signal = order_details["action"] # 'buy' or 'sell'
            current_position = self.portfolio_manager.get_position(symbol)

            # --- Logic for BUY signal ---
            if signal == "buy":
                if current_position and current_position.side == "short":
                    # Close the short position before opening a long one
                    log.info("trader.execute_order.close_short_open_long", extra={"extra": {"symbol": symbol}})
                    self.broker.close_position(symbol)
                    current_position = None # Position is now closed

                # Proceed if no position exists or if we are adding to a long position
                if not current_position or current_position.side == "long":
                    log.info("trader.execute_order.open_or_add_long", extra={"extra": {"symbol": symbol}})
                    qty, current_price = self.risk_manager.calculate_order_qty(symbol, "buy", historical_data)
                    if qty > 0:
                        order_request = self.risk_manager.generate_bracket_order(
                            symbol=symbol, qty=qty, side="buy", current_price=current_price, historical_data=historical_data
                        )
                        self.broker.submit_order(order_request)

            # --- Logic for SELL signal (shorting) ---
            elif signal == "sell":
                if current_position and current_position.side == "long":
                    # Close the long position before opening a short one
                    log.info("trader.execute_order.close_long_open_short", extra={"extra": {"symbol": symbol}})
                    self.broker.close_position(symbol)
                    current_position = None # Position is now closed

                # Proceed if no position exists or if we are adding to a short position
                if not current_position or current_position.side == "short":
                    log.info("trader.execute_order.open_or_add_short", extra={"extra": {"symbol": symbol}})
                    qty, current_price = self.risk_manager.calculate_order_qty(symbol, "sell", historical_data)
                    if qty > 0:
                        order_request = self.risk_manager.generate_bracket_order(
                            symbol=symbol, qty=qty, side="sell", current_price=current_price, historical_data=historical_data
                        )
                        self.broker.submit_order(order_request)

        except Exception:
            log.error("trader.execute_order.fail", exc_info=True)


