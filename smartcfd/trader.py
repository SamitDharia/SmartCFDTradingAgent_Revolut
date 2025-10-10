import logging
from typing import List, Dict, Any, Optional
import pandas as pd
import time

from .strategy import Strategy, InferenceStrategy, get_strategy_by_name
from .broker import Broker
from .risk import RiskManager
from .portfolio import PortfolioManager
from .regime_detector import RegimeDetector, MarketRegime
from .data_loader import DataLoader
from .trade_group_manager import TradeGroupManager
from smartcfd.alpaca_client import AlpacaBroker
from .types import TradeGroup
from alpaca_trade_api.entity import Order

log = logging.getLogger(__name__)

class Trader:
    """
    The Trader class orchestrates the trading process.
    It uses a Strategy to get trading signals and a Broker to execute them.
    A RiskManager is used to size the orders.
    """

    def __init__(self, app_config: Any, risk_config: Any, regime_config: Any, broker: AlpacaBroker, db_conn: Any, portfolio_manager: PortfolioManager, risk_manager: RiskManager):
        self.app_config = app_config
        self.risk_config = risk_config
        self.regime_config = regime_config
        self.broker = broker
        self.db_conn = db_conn
        self.portfolio_manager = portfolio_manager
        self.risk_manager = risk_manager
        self.regime_detector = RegimeDetector(app_config, regime_config)
        self.strategy = self._initialize_strategy(app_config)
        self.trade_group_manager = TradeGroupManager(db_conn)

        self.reconcile_on_start = self.app_config.on_reconnect_reconcile

    def _initialize_strategy(self, app_config: Any) -> Strategy:
        """
        Initializes the trading strategy based on the app configuration.
        """
        strategy_name = app_config.strategy
        log.info(f"Initializing strategy: {strategy_name}")
        
        # Pass both app_config and broker to the strategy factory
        return get_strategy_by_name(strategy_name, app_config, self.broker)

    def run(self):
        """
        Runs the trading loop, which is now a stateful reconciliation loop.
        """
        try:
            # 1. Reconcile our internal state with the broker
            # self.reconcile_trade_groups()

            # 2. Reconcile portfolio state with the broker
            self.portfolio_manager.reconcile()

            # 3. Look for new trading opportunities
            self.evaluate_new_trades()

        except Exception:
            log.error("trader.run.fail", exc_info=True)

    def reconcile_trade_groups(self, historical_data: Dict[str, pd.DataFrame]):
        """
        Reconciles the state of all trade groups, including arming exits for filled entries.
        """
        log.info("trader.reconcile_trade_groups.start")
        trade_groups = self.trade_group_manager.get_all_trade_groups()
        for group in trade_groups:
            if group.status == "ENTRY_ORDER_PLACED":
                # Check if the entry order has been filled
                entry_order = self.broker.get_order_by_client_id(group.entry_order_id)
                if entry_order and entry_order.status == 'filled':
                    log.info("trader.arm_exits.entry_filled", extra={"extra": {"group_id": group.id, "symbol": group.symbol}})
                    self.arm_exits(group, entry_order, historical_data)
    
    def arm_exits(self, group: TradeGroup, entry_order: Order, historical_data: Dict[str, pd.DataFrame]):
        """
        Arms the take-profit and stop-loss orders for a filled entry order.
        """
        symbol_data = historical_data.get(group.symbol)
        if symbol_data is None or symbol_data.empty:
            log.error("trader.arm_exits.no_historical_data", extra={"extra": {"group_id": group.id, "symbol": group.symbol}})
            return

        # Now we have data, calculate and place exit orders
        try:
            exit_orders = self.risk_manager.generate_exit_orders(
                symbol=group.symbol,
                entry_price=float(entry_order.filled_avg_price),
                qty=float(entry_order.filled_qty),
                side=entry_order.side,
                historical_data=symbol_data
            )
            
            if not exit_orders:
                log.error("trader.arm_exits.exit_order_generation_failed", extra={"extra": {"group_id": group.id}})
                return

            tp_order_data = exit_orders['take_profit']
            sl_order_data = exit_orders['stop_loss']

            # Create a unique client_order_id for the OCO group
            client_order_id_base = f"oco_{group.id}_{int(time.time())}"
            tp_order_data['client_order_id'] = f"{client_order_id_base}_tp"
            sl_order_data['client_order_id'] = f"{client_order_id_base}_sl"

            # Submit the OCO (One-Cancels-Other) order
            # Note: Alpaca API doesn't have a native OCO for crypto.
            # We will submit two separate orders and manage the cancellation logic ourselves.
            
            # Submit Take Profit
            tp_order = self.broker.submit_order(tp_order_data)
            
            # Submit Stop Loss
            sl_order = self.broker.submit_order(sl_order_data)

            if tp_order and sl_order:
                self.db_conn.update_trade_group_exits(group.id, tp_order.id, sl_order.id)
                self.db_conn.update_trade_group_status(group.id, "ACTIVE")
                log.info("trader.arm_exits.success", extra={"extra": {"group_id": group.id, "tp_order_id": tp_order.id, "sl_order_id": sl_order.id}})
            else:
                # This requires rollback logic, which is complex. For now, log critical error.
                log.critical("trader.arm_exits.partial_exit_submission", extra={"extra": {"group_id": group.id, "tp_order": tp_order, "sl_order": sl_order}})

        except Exception as e:
            log.error("trader.arm_exits.exception", exc_info=True, extra={"extra": {"group_id": group.id}})

    def evaluate_new_trades(self):
        """
        Evaluates the strategy for new trading opportunities and executes them.
        """
        watch_list = self.app_config.watch_list.split(',')
        
        # First, get historical data. The strategy's evaluate method is now responsible for this.
        historical_data = self.strategy.get_historical_data(watch_list)

        # Now that we have data, we can reconcile trade groups, which may need to arm exits
        self.reconcile_trade_groups(historical_data)

        # If the initial data load failed or returned no valid data, we should not proceed.
        if not historical_data or all(df.empty for df in historical_data.values()):
            log.warning("trader.run.no_valid_data_from_strategy")
            return

        # Check for global halt conditions (e.g., max drawdown, high volatility)
        halted = self.risk_manager.check_for_halt(historical_data, self.app_config.trade_interval)
        if halted:
            log.critical("trader.run.halted", extra={"extra": {"reason": self.risk_manager.halt_reason}})
            return

        # Detect market regime for each symbol
        market_regimes = {}
        for symbol, data in historical_data.items():
            if not data.empty:
                regime = self.regime_detector.detect(data)
                market_regimes[symbol] = regime
            else:
                log.warning("trader.run.no_data_for_regime_detection", extra={"extra": {"symbol": symbol}})

        # If no regimes were detected, we cannot proceed with the strategy.
        if not market_regimes:
            log.warning("trader.run.no_regimes_detected")
            return

        # Now, get trading signals from the strategy using the data and regimes
        actions = []
        for symbol in watch_list:
            if symbol in historical_data and symbol in market_regimes:
                action = self.strategy.evaluate(
                    symbol=symbol,
                    regime=market_regimes[symbol],
                    historical_data=historical_data[symbol]
                )
                if action:
                    actions.append(action)

        # Execute actions
        self.execute_actions(actions, historical_data)

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
            
            elif action_type == "trade":
                # Check if there is already an active trade group for this symbol
                # Note: This check might need refinement. Do we allow multiple positions?
                # For now, we prevent new trades if one is active.
                active_groups = self.trade_group_manager.get_groups_by_status("ACTIVE")
                if any(g.symbol == symbol for g in active_groups):
                    log.info("trader.execute_order.already_active", extra={"extra": {"symbol": symbol}})
                    continue

                # Perform volatility check before executing a trade order
                if symbol and symbol in historical_data and self.risk_manager.is_volatility_too_high(historical_data[symbol], symbol):
                    log.warning("trader.execute_order.halted_volatility", 
                                extra={"extra": {"symbol": symbol, "reason": "Circuit breaker tripped due to high volatility."}})
                    continue # Skip this action

                self.initiate_trade(action, historical_data.get(symbol))

            else:
                log.warning("trader.execute_actions.unknown_action", extra={"extra": {"action_type": action_type}})

    def initiate_trade(self, trade_details: Dict[str, Any], historical_data: Optional[pd.DataFrame]):
        """
        Initiates a new trade by creating a trade group and submitting the entry order.
        """
        try:
            symbol = trade_details["symbol"]
            side = trade_details["side"] # 'buy' or 'sell'
            
            # Create a new trade group
            group = self.trade_group_manager.create_group(symbol, side)
            if not group:
                log.error("trader.initiate_trade.group_creation_failed", extra={"extra": {"symbol": symbol, "side": side}})
                return

            # Calculate order quantity
            qty, current_price = self.risk_manager.calculate_order_qty(symbol, side, historical_data)
            if qty <= 0:
                log.warning("trader.initiate_trade.zero_or_neg_qty", extra={"extra": {"symbol": symbol, "qty": qty}})
                self.trade_group_manager.update_group_status(group.id, "CANCELLED", "Zero quantity calculated")
                return

            # Generate the simple market order request
            order_request = self.risk_manager.generate_entry_order(
                symbol=symbol, qty=qty, side=side
            )
            
            if not order_request:
                log.error("trader.initiate_trade.order_request_failed", extra={"extra": {"group_id": group.id}})
                self.trade_group_manager.update_group_status(group.id, "FAILED", "Order request generation failed")
                return

            # Tag the order with our Group ID for tracking
            order_request['client_order_id'] = f"{group.id}_entry"

            # Submit the entry order
            entry_order = self.broker.submit_order(order_request)

            # Update the trade group with the entry order ID and set status to pending
            if entry_order and entry_order.id:
                self.trade_group_manager.update_trade_group_entry(group.id, entry_order.id)
                self.trade_group_manager.update_trade_group_status(group.id, "ENTRY_ORDER_PLACED")
                log.info("trader.initiate_trade.success", extra={"extra": {"group_id": group.id, "entry_order_id": entry_order.id}})
            else:
                log.error("trader.initiate_trade.order_submission_failed", extra={"extra": {"group_id": group.id}})
                self.trade_group_manager.update_group_status(group.id, "FAILED", "Entry order submission failed")

        except Exception:
            log.error("trader.initiate_trade.fail", exc_info=True)


