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
from time import sleep
from smartcfd.db import record_order_event
from smartcfd.indicators import atr

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
                    log.info("trader.arm_exits.entry_filled", extra={"extra": {"group_id": group.gid, "symbol": group.symbol}})
                    try:
                        record_order_event(
                            self.db_conn,
                            event_type="entry_filled",
                            group_gid=group.gid,
                            symbol=group.symbol,
                            order_client_id=group.entry_order_id,
                            broker_order_id=getattr(entry_order, 'id', None),
                            side=getattr(entry_order, 'side', None),
                            qty=float(getattr(entry_order, 'filled_qty', 0) or 0),
                            price=float(getattr(entry_order, 'filled_avg_price', 0) or 0),
                            status=getattr(entry_order, 'status', None),
                        )
                    except Exception:
                        pass
                    self.arm_exits(group, entry_order, historical_data)
            elif group.status == "ACTIVE":
                # Manage OCO exits: if one is filled, cancel the other and close
                try:
                    tp_cid = group.tp_order_id
                    sl_cid = group.sl_order_id
                    tp_order = self.broker.get_order_by_client_id(tp_cid) if tp_cid else None
                    sl_order = self.broker.get_order_by_client_id(sl_cid) if sl_cid else None

                    def _is_open(o):
                        return o is not None and str(getattr(o, 'status', '')).lower() in ("new", "accepted", "open", "partially_filled", "pending_cancel")

                    status_tp = str(getattr(tp_order, 'status', '')).lower() if tp_order else ''
                    status_sl = str(getattr(sl_order, 'status', '')).lower() if sl_order else ''
                    tp_filled = status_tp == 'filled'
                    sl_filled = status_sl == 'filled'
                    tp_partial = status_tp == 'partially_filled'
                    sl_partial = status_sl == 'partially_filled'

                    def _cancel_with_backoff(order_id: str) -> bool:
                        delays = [0.5, 1.0, 2.0]
                        for i, d in enumerate(delays):
                            try:
                                log.info("orders.lifecycle.cancel_attempt", extra={"extra": {"order_id": order_id, "attempt": i+1}})
                                self.broker.cancel_order(order_id)
                                log.info("orders.lifecycle.cancel_success", extra={"extra": {"order_id": order_id}})
                                return True
                            except Exception:
                                log.warning("orders.lifecycle.cancel_retry", exc_info=True, extra={"extra": {"order_id": order_id, "backoff_s": d}})
                                sleep(d)
                        log.error("orders.lifecycle.cancel_failed", extra={"extra": {"order_id": order_id}})
                        return False

                    if tp_filled:
                        if _is_open(sl_order):
                            _cancel_with_backoff(sl_order.id)
                            try:
                                record_order_event(self.db_conn, "exit_cancelled_sl", group.gid, group.symbol, sl_cid, getattr(sl_order, 'id', None), note="peer_tp_filled")
                            except Exception:
                                pass
                        self.trade_group_manager.update_trade_group_status(group.gid, "CLOSED", note="tp_filled")
                        try:
                            record_order_event(self.db_conn, "group_closed", group.gid, group.symbol, status="tp_filled")
                        except Exception:
                            pass
                        log.info("trader.reconcile_trade_groups.closed_tp", extra={"extra": {"group_id": group.gid}})
                    elif sl_filled:
                        if _is_open(tp_order):
                            _cancel_with_backoff(tp_order.id)
                            try:
                                record_order_event(self.db_conn, "exit_cancelled_tp", group.gid, group.symbol, tp_cid, getattr(tp_order, 'id', None), note="peer_sl_filled")
                            except Exception:
                                pass
                        self.trade_group_manager.update_trade_group_status(group.gid, "CLOSED", note="sl_filled")
                        try:
                            record_order_event(self.db_conn, "group_closed", group.gid, group.symbol, status="sl_filled")
                        except Exception:
                            pass
                        log.info("trader.reconcile_trade_groups.closed_sl", extra={"extra": {"group_id": group.gid}})
                    elif tp_partial or sl_partial:
                        # Partial exit: adjust the peer order qty and refresh price using ATR if possible
                        pos = self.portfolio_manager.get_position(group.symbol)
                        rem_qty = float(getattr(pos, 'qty', 0.0) or 0.0)
                        peer = sl_order if tp_partial else tp_order
                        if rem_qty > 0 and peer is not None and _is_open(peer):
                            # Compute ATR-based refreshed price from provided historical data
                            symbol_df = historical_data.get(group.symbol)
                            new_limit = None
                            new_stop = None
                            try:
                                if symbol_df is not None and not symbol_df.empty:
                                    current_close = float(symbol_df['close'].iloc[-1])
                                    current_atr = float(atr(symbol_df['high'], symbol_df['low'], symbol_df['close'], window=14).iloc[-1])
                                    if tp_partial:
                                        # Peer is SL
                                        if group.side == 'buy':
                                            new_stop = current_close - (current_atr * self.risk_config.stop_loss_atr_multiplier)
                                        else:
                                            new_stop = current_close + (current_atr * self.risk_config.stop_loss_atr_multiplier)
                                    else:
                                        # sl_partial, peer is TP
                                        if group.side == 'buy':
                                            new_limit = current_close + (current_atr * self.risk_config.take_profit_atr_multiplier)
                                        else:
                                            new_limit = current_close - (current_atr * self.risk_config.take_profit_atr_multiplier)
                            except Exception:
                                pass

                            try:
                                self.broker.replace_order(
                                    peer.id,
                                    qty=str(rem_qty),
                                    limit_price=(str(round(new_limit, 2)) if new_limit is not None else None),
                                    stop_price=(str(round(new_stop, 2)) if new_stop is not None else None),
                                )
                                log.info("orders.lifecycle.replace_success", extra={"extra": {"order_id": peer.id, "new_qty": rem_qty, "new_limit": new_limit, "new_stop": new_stop}})
                                try:
                                    record_order_event(self.db_conn, "replace_success", group.gid, group.symbol, broker_order_id=getattr(peer, 'id', None), qty=rem_qty, price=new_limit or new_stop)
                                except Exception:
                                    pass
                            except Exception:
                                log.warning("orders.lifecycle.replace_fail", exc_info=True, extra={"extra": {"order_id": peer.id, "new_qty": rem_qty, "new_limit": new_limit, "new_stop": new_stop}})
                                try:
                                    record_order_event(self.db_conn, "replace_fail", group.gid, group.symbol, broker_order_id=getattr(peer, 'id', None), qty=rem_qty, price=new_limit or new_stop)
                                except Exception:
                                    pass
                            self.trade_group_manager.update_trade_group_status(group.gid, "PARTIAL_EXIT")
                            log.info("orders.lifecycle.partial_exit", extra={"extra": {"group_id": group.gid, "tp_status": status_tp, "sl_status": status_sl, "rem_qty": rem_qty}})
                        else:
                            # No remaining qty or peer not open: close out group and ensure peer is cancelled
                            if peer is not None and _is_open(peer):
                                _cancel_with_backoff(peer.id)
                                try:
                                    record_order_event(self.db_conn, "exit_cancelled_peer_after_partial", group.gid, group.symbol, broker_order_id=getattr(peer, 'id', None))
                                except Exception:
                                    pass
                            self.trade_group_manager.update_trade_group_status(group.gid, "CLOSED", note="partial_exit_no_remaining")
                            try:
                                record_order_event(self.db_conn, "group_closed", group.gid, group.symbol, status="partial_exit_no_remaining")
                            except Exception:
                                pass
                            log.info("orders.lifecycle.partial_exit_closed", extra={"extra": {"group_id": group.gid}})
                except Exception:
                    log.error("trader.reconcile_trade_groups.manage_oco_fail", exc_info=True, extra={"extra": {"group_id": group.gid}})
    
    def arm_exits(self, group: TradeGroup, entry_order: Order, historical_data: Dict[str, pd.DataFrame]):
        """
        Arms the take-profit and stop-loss orders for a filled entry order.
        """
        symbol_data = historical_data.get(group.symbol)
        if symbol_data is None or symbol_data.empty:
            log.error("trader.arm_exits.no_historical_data", extra={"extra": {"group_id": group.gid, "symbol": group.symbol}})
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
                log.error("trader.arm_exits.exit_order_generation_failed", extra={"extra": {"group_id": group.gid}})
                return

            tp_order_data = exit_orders['take_profit']
            sl_order_data = exit_orders['stop_loss']

            # Create a unique client_order_id for the OCO group
            client_order_id_base = f"oco_{group.gid}_{int(time.time())}"
            tp_order_data['client_order_id'] = f"{client_order_id_base}_tp"
            sl_order_data['client_order_id'] = f"{client_order_id_base}_sl"

            # Submit the OCO (One-Cancels-Other) order
            # Note: Alpaca API doesn't have a native OCO for crypto.
            # We will submit two separate orders and manage the cancellation logic ourselves.
            
            # Submit Take Profit
            # Submit via dedicated broker helpers (Alpaca crypto lacks native OCO)
            tp_order = self.broker.submit_take_profit_order(
                symbol=tp_order_data["symbol"],
                qty=str(tp_order_data["qty"]),
                side=tp_order_data["side"],
                price=str(tp_order_data["limit_price"]),
                client_order_id=tp_order_data["client_order_id"],
            )

            sl_order = self.broker.submit_stop_loss_order(
                symbol=sl_order_data["symbol"],
                qty=str(sl_order_data["qty"]),
                side=sl_order_data["side"],
                price=str(sl_order_data["stop_price"]),
                client_order_id=sl_order_data["client_order_id"],
            )

            if tp_order and sl_order:
                # Store client order IDs (not broker-generated IDs) for robust lookup
                self.trade_group_manager.update_trade_group_exits(group.gid, tp_order_data['client_order_id'], sl_order_data['client_order_id'])
                self.trade_group_manager.update_trade_group_status(group.gid, "ACTIVE")
                log.info("trader.arm_exits.success", extra={"extra": {"group_id": group.gid, "tp_client_id": tp_order_data['client_order_id'], "sl_client_id": sl_order_data['client_order_id']}})
                try:
                    record_order_event(self.db_conn, "exit_submit_tp", group.gid, group.symbol, tp_order_data['client_order_id'], getattr(tp_order, 'id', None), side="sell" if entry_order.side=="buy" else "buy", order_kind="limit", qty=float(tp_order_data['qty']), price=float(tp_order_data['limit_price']))
                    record_order_event(self.db_conn, "exit_submit_sl", group.gid, group.symbol, sl_order_data['client_order_id'], getattr(sl_order, 'id', None), side="sell" if entry_order.side=="buy" else "buy", order_kind="stop", qty=float(sl_order_data['qty']), price=float(sl_order_data['stop_price']))
                except Exception:
                    pass
            else:
                # This requires rollback logic, which is complex. For now, log critical error.
                log.critical("trader.arm_exits.partial_exit_submission", extra={"extra": {"group_id": group.gid, "tp_order": str(bool(tp_order)), "sl_order": str(bool(sl_order))}})

        except Exception as e:
            log.error("trader.arm_exits.exception", exc_info=True, extra={"extra": {"group_id": group.gid}})

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
                    action['symbol'] = symbol # Add symbol to action dict
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
                if symbol and symbol in historical_data and self.risk_manager.volatility_check(historical_data[symbol], symbol):
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
                self.trade_group_manager.update_group_status(group.gid, "CANCELLED", "Zero quantity calculated")
                return

            # Generate the simple market order request
            order_request = self.risk_manager.generate_entry_order(
                symbol=symbol, qty=qty, side=side
            )
            
            if not order_request:
                log.error("trader.initiate_trade.order_request_failed", extra={"extra": {"group_id": group.gid}})
                self.trade_group_manager.update_group_status(group.gid, "FAILED", "Order request generation failed")
                return

            # Tag the order with our Group ID for tracking
            order_request['client_order_id'] = f"{group.gid}_entry"
            try:
                record_order_event(
                    self.db_conn,
                    event_type="entry_submit",
                    group_gid=group.gid,
                    symbol=symbol,
                    order_client_id=order_request['client_order_id'],
                    side=side,
                    order_kind="market",
                    qty=float(qty),
                )
            except Exception:
                pass

            # Submit the entry order
            from smartcfd.types import OrderRequest as _OrderRequest
            try:
                entry_order = self.broker.submit_order(_OrderRequest(**order_request))
                try:
                    record_order_event(
                        self.db_conn,
                        event_type="entry_submitted",
                        group_gid=group.gid,
                        symbol=symbol,
                        order_client_id=order_request['client_order_id'],
                        broker_order_id=getattr(entry_order, 'id', None),
                        side=side,
                        order_kind="market",
                        qty=float(qty),
                        status=getattr(entry_order, 'status', None),
                    )
                except Exception:
                    pass
            except Exception:
                log.error("trader.initiate_trade.order_build_fail", exc_info=True, extra={"extra": {"group_id": group.gid}})
                self.trade_group_manager.update_group_status(group.gid, "FAILED", "Entry order build failed")
                return

            # Update the trade group with the entry order ID and set status to pending
            if entry_order and getattr(entry_order, 'id', None):
                # Store the client_order_id so we can query by client ID later
                self.trade_group_manager.update_trade_group_entry(group.gid, order_request['client_order_id'])
                self.trade_group_manager.update_trade_group_status(group.gid, "ENTRY_ORDER_PLACED")
                log.info("trader.initiate_trade.success", extra={"extra": {"group_id": group.gid, "entry_order_id": entry_order.id, "client_order_id": order_request['client_order_id']}})
            else:
                log.error("trader.initiate_trade.order_submission_failed", extra={"extra": {"group_id": group.gid}})
                self.trade_group_manager.update_group_status(group.gid, "FAILED", "Entry order submission failed")

        except Exception:
            log.error("trader.initiate_trade.fail", exc_info=True)


