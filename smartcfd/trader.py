import logging
from typing import List, Dict, Any, Optional
import pandas as pd

from .strategy import Strategy
from .broker import Broker
from .risk import RiskManager
from .portfolio import PortfolioManager
from .regime_detector import RegimeDetector, MarketRegime
from .data_loader import DataLoader

log = logging.getLogger(__name__)

class Trader:
    """
    The Trader class orchestrates the trading process.
    It uses a Strategy to get trading signals and a Broker to execute them.
    A RiskManager is used to size the orders.
    """

    def __init__(self, portfolio_manager: PortfolioManager, strategy: Strategy, risk_manager: RiskManager, app_config: Any, regime_detector: RegimeDetector, alpaca_config: Any):
        self.portfolio_manager = portfolio_manager
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.app_config = app_config
        self.regime_detector = regime_detector
        # The broker client is now accessed via the portfolio manager
        self.broker = portfolio_manager.client
        self.data_loader = DataLoader(
            api_key=alpaca_config.api_key,
            secret_key=alpaca_config.secret_key,
            api_base="https://paper-api.alpaca.markets" if app_config.alpaca_env == "paper" else "https://api.alpaca.markets"
        )
        # Pass the data loader to the strategy
        self.strategy.data_loader = self.data_loader

    def run(self):
        """
        Runs the trading loop.
        """
        watch_list = self.app_config.watch_list.split(',')
        interval = self.app_config.trade_interval
        try:
            # 1. Reconcile portfolio state with the broker
            self.portfolio_manager.reconcile()

            # 2. First Pass: Evaluate strategy to get historical data for regime detection and risk checks
            actions, historical_data = self.strategy.evaluate(
                self.portfolio_manager, 
                watch_list,
                market_regimes=None # Pass None to signal data gathering pass
            )

            # If the initial data load failed or returned no valid data, we should not proceed.
            if not historical_data or all(df.empty for df in historical_data.values()):
                log.warning("trader.run.no_valid_data_from_strategy")
                return

            # 3. Check for global halt conditions (e.g., max drawdown, high volatility)
            halted = self.risk_manager.check_for_halt(historical_data, interval)
            if halted:
                log.critical("trader.run.halted", extra={"extra": {"reason": self.risk_manager.halt_reason}})
                return

            # 4. Detect market regime for each symbol
            market_regimes = {}
            for symbol, data in historical_data.items():
                if not data.empty:
                    regime = self.regime_detector.detect_regime(data)
                    market_regimes[symbol] = regime
                else:
                    log.warning("trader.run.no_data_for_regime_detection", extra={"extra": {"symbol": symbol}})

            # If no regimes were detected, we cannot proceed with the strategy.
            if not market_regimes:
                log.warning("trader.run.no_regimes_detected")
                return

            # 5. Second Pass: Re-evaluate strategy with regime context to get final actions
            actions, _ = self.strategy.evaluate( # We already have the data
                self.portfolio_manager, 
                watch_list, 
                market_regimes,
                historical_data=historical_data # Pass the data from the first run
            )

            # 6. Execute actions
            self.execute_actions(actions, historical_data)
        except Exception:
            log.error("trader.run.fail", exc_info=True)

    def execute_actions(self, actions: List[Dict[str, Any]], historical_data: Dict[str, pd.DataFrame]):
        """
        Executes a list of actions received from the strategy, after risk checks.
        """
        if not actions:
            log.info("trader.execute_actions.no_actions")
            return

        for action in actions:
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
                    self.broker.close_position(symbol)
                    current_position = None # Position is now closed

                # Proceed if no position exists or if we are adding to a long position
                if not current_position or current_position.side == "long":
                    qty, current_price = self.risk_manager.calculate_order_qty(symbol, "buy", historical_data)
                    if qty > 0:
                        order_request = self.risk_manager.generate_bracket_order(
                            symbol=symbol, qty=qty, side="buy", current_price=current_price, historical_data=historical_data
                        )
                        if order_request:
                            self.broker.submit_order(order_request)

            # --- Logic for SELL signal (shorting) ---
            elif signal == "sell":
                if current_position and current_position.side == "long":
                    # Close the long position before opening a short one
                    self.broker.close_position(symbol)
                    current_position = None # Position is now closed

                # Proceed if no position exists or if we are adding to a short position
                if not current_position or current_position.side == "short":
                    qty, current_price = self.risk_manager.calculate_order_qty(symbol, "sell", historical_data)
                    if qty > 0:
                        order_request = self.risk_manager.generate_bracket_order(
                            symbol=symbol, qty=qty, side="sell", current_price=current_price, historical_data=historical_data
                        )
                        if order_request:
                            self.broker.submit_order(order_request)

        except Exception:
            log.error("trader.execute_order.fail", exc_info=True)


