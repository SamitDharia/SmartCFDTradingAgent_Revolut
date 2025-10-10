import logging
from typing import List, Dict, Any, Optional, Tuple, Tuple, Tuple
import pandas as pd
from pydantic import BaseModel
import ta

from smartcfd.types import OrderRequest, StopLossRequest, TakeProfitRequest
from smartcfd.config import RiskConfig
from smartcfd.data_loader import DataLoader
from smartcfd.db import get_daily_pnl
from smartcfd.indicators import atr
from smartcfd.strategy import Strategy
from smartcfd.portfolio import Account, Position, PortfolioManager
from smartcfd.backtest_portfolio import BacktestPortfolio

log = logging.getLogger("risk")

class RiskManager:
    """
    Manages and enforces risk rules for trading.
    """
    def __init__(self, portfolio_manager: PortfolioManager, risk_config: RiskConfig, broker=None):
        self.portfolio_manager = portfolio_manager
        self.config = risk_config
        self.is_halted = False
        self.halt_reason = ""
        self.broker = broker


    def generate_bracket_order(self, symbol: str, side: str, qty: float, current_price: float, historical_data: pd.DataFrame) -> Optional[OrderRequest]:
        """
        Generates a complete bracket order request with stop-loss and take-profit levels.
        """
        if qty <= 0:
            return None

        try:
            # Ensure qty is a float for calculations
            qty = float(qty)

            if not current_price or current_price <= 0:
                log.error("risk.generate_bracket_order.no_price", extra={"extra": {"symbol": symbol}})
                return None

            # Calculate ATR for stop-loss
            try:
                atr = ta.volatility.average_true_range(high=historical_data['high'], low=historical_data['low'], close=historical_data['close'], window=14).iloc[-1]
            except Exception:
                log.error("risk.generate_bracket_order.atr_fail", extra={"extra": {"symbol": symbol}}, exc_info=True)
                return None

            if atr <= 0:
                log.warning("risk.generate_bracket_order.invalid_atr", extra={"extra": {"symbol": symbol, "atr": atr}})
                return None

            # --- Calculate Stop-Loss and Take-Profit Prices ---
            stop_loss_risk = atr * self.config.stop_loss_atr_multiplier
            
            if side == "buy":
                stop_price = current_price - stop_loss_risk
                take_profit_price = current_price + (atr * self.config.take_profit_atr_multiplier)
            else:  # sell
                stop_price = current_price + stop_loss_risk
                take_profit_price = current_price - (atr * self.config.take_profit_atr_multiplier)

            # --- Construct Order Request ---
            # Alpaca API for crypto does not support bracket orders.
            # We will submit a market order and then two separate OCO (One-Cancels-Other) orders for SL/TP.
            # This logic will be handled by the trader. For now, we create a simple market order.
            order_request = OrderRequest(
                symbol=symbol,
                qty=str(qty),
                side=side,
                type="market",
                time_in_force="gtc",
            )

            # We will still calculate the SL/TP prices and attach them to the request
            # so the trader can use them.
            order_request.stop_loss = StopLossRequest(stop_price=str(round(stop_price, 2)))
            order_request.take_profit = TakeProfitRequest(limit_price=str(round(take_profit_price, 2)))

            log_extra = order_request.model_dump()
            if order_request.stop_loss:
                log_extra['stop_loss'] = order_request.stop_loss.model_dump()
            if order_request.take_profit:
                log_extra['take_profit'] = order_request.take_profit.model_dump()
            
            log.info("risk.generate_bracket_order.success", extra={"extra": log_extra})
            return order_request
        except Exception:
            log.error("risk.generate_bracket_order.fail", exc_info=True)
            return None

    def generate_entry_order(self, symbol: str, side: str, qty: float) -> Optional[Dict[str, Any]]:
        """
        Generates a simple market order for market entry.
        """
        if qty <= 0:
            return None
        
        order_request = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": "market",
            "time_in_force": "gtc",
        }
        log.info("risk.generate_entry_order.success", extra={"extra": order_request})
        return order_request

    def calculate_order_qty(self, symbol: str, side: str, historical_data: Optional[pd.DataFrame]) -> Tuple[float, float]:
        """
        Calculates the quantity for an order based on risk rules and returns
        the quantity and the current price.
        """
        log.info(
            "risk.calculate_order_qty.start",
            extra={"extra": {"symbol": symbol, "side": side}},
        )

        if self.is_halted:
            log.warning(
                "risk.calculate_order_qty.halted",
                extra={"extra": {"reason": self.halt_reason, "symbol": symbol}},
            )
            return 0.0, 0.0

        account = self.portfolio_manager.account
        if not account or not account.is_online:
            log.error(
                "risk.calculate_order_qty.no_account",
                extra={"extra": {"reason": "Cannot calculate quantity without online account info."}},
            )
            return 0.0, 0.0

        try:
            account = self.portfolio_manager.account
            if not account:
                log.error("risk.calculate_order_qty.no_account")
                return 0.0, 0.0

            # Get current price from the historical data that was passed in
            if historical_data is None or historical_data.empty:
                log.error("risk.calculate_order_qty.no_data", extra={"extra": {"symbol": symbol}})
                return 0.0, 0.0
            current_price = historical_data['close'].iloc[-1]

            if not current_price or current_price <= 0:
                log.error("risk.calculate_order_qty.no_price", extra={"extra": {"symbol": symbol}})
                return 0.0, 0.0

            # Rule 1: Max total exposure
            equity = float(account.equity)
            max_total_exposure_value = equity * (self.config.max_total_exposure_percent / 100.0)
            
            # Use absolute value for exposure calculation
            total_exposure = float(self.portfolio_manager.get_total_exposure())

            log.info(f"EQUITY: {equity}, TOTAL_EXPOSURE: {total_exposure}, MAX_EXPOSURE: {max_total_exposure_value}")
            
            available_capital_total = max_total_exposure_value - total_exposure
            if available_capital_total <= 0:
                log.warning("risk.calculate_order_qty.max_total_exposure_breached", 
                            extra={"extra": {"total_exposure": total_exposure, "max_total_notional": max_total_exposure_value}})
                return 0.0, current_price

            # Rule 2: Max exposure per asset
            max_asset_exposure_value = equity * (self.config.max_exposure_per_asset_percent / 100.0)
            
            # Use absolute value for exposure calculation
            current_asset_exposure = float(self.portfolio_manager.get_exposure_for_symbol(symbol))
            
            available_capital_asset = max_asset_exposure_value - current_asset_exposure
            if available_capital_asset <= 0:
                log.warning("risk.calculate_order_qty.max_asset_exposure_breached",
                            extra={"extra": {"symbol": symbol, "current_exposure": current_asset_exposure, "max_notional": max_asset_exposure_value}})
                return 0.0, current_price

            # Rule 3: Risk per trade
            risk_per_trade_value = equity * (self.config.risk_per_trade_percent / 100.0)

            # Determine the final capital to allocate
            capital_to_allocate = min(
                available_capital_total,
                available_capital_asset,
                risk_per_trade_value,
            )

            if capital_to_allocate < self.config.min_order_notional:
                log.warning(
                    "risk.calculate_order_qty.below_min_notional",
                    extra={"extra": {"capital_to_allocate": capital_to_allocate, "min_order_notional": self.config.min_order_notional}},
                )
                return 0.0, current_price

            qty = capital_to_allocate / current_price

            log.info(
                "risk.calculate_order_qty.success",
                extra={"extra": {"symbol": symbol, "qty": qty, "price": current_price}},
            )
            return qty, current_price
        except Exception:
            log.error("risk.calculate_order_qty.fail", exc_info=True)
            return 0.0, 0.0

    def generate_exit_orders(self, symbol: str, entry_price: float, qty: float, side: str, historical_data: pd.DataFrame) -> Optional[Dict[str, Dict]]:
        """
        Generates take-profit and stop-loss order parameters based on ATR.
        """
        if historical_data.empty:
            log.error("risk.generate_exit_orders.no_data")
            return None

        try:
            # Ensure 'atr' is calculated if not present
            if 'atr' not in historical_data.columns:
                # Assuming 'high', 'low', 'close' are present for ATR calculation
                from smartcfd.indicators import atr
                historical_data['atr'] = atr(historical_data['high'], historical_data['low'], historical_data['close'], length=14)

            current_atr = historical_data['atr'].iloc[-1]
            
            if side == 'buy':
                # For a buy order, TP is above entry, SL is below
                take_profit_price = entry_price + (current_atr * self.config.take_profit_atr_multiplier)
                stop_loss_price = entry_price - (current_atr * self.config.stop_loss_atr_multiplier)
                
                tp_order = {
                    "symbol": symbol,
                    "qty": qty,
                    "side": "sell",
                    "type": "limit",
                    "limit_price": round(take_profit_price, 2),
                    "order_class": "oto", # One-Triggers-Other
                    "time_in_force": "gtc"
                }
                sl_order = {
                    "symbol": symbol,
                    "qty": qty,
                    "side": "sell",
                    "type": "stop",
                    "stop_price": round(stop_loss_price, 2),
                    "order_class": "oto",
                    "time_in_force": "gtc"
                }
            else: # side == 'sell'
                # For a sell order, TP is below entry, SL is above
                take_profit_price = entry_price - (current_atr * self.config.take_profit_atr_multiplier)
                stop_loss_price = entry_price + (current_atr * self.config.stop_loss_atr_multiplier)

                tp_order = {
                    "symbol": symbol,
                    "qty": qty,
                    "side": "buy",
                    "type": "limit",
                    "limit_price": round(take_profit_price, 2),
                    "order_class": "oto",
                    "time_in_force": "gtc"
                }
                sl_order = {
                    "symbol": symbol,
                    "qty": qty,
                    "side": "buy",
                    "type": "stop",
                    "stop_price": round(stop_loss_price, 2),
                    "order_class": "oto",
                    "time_in_force": "gtc"
                }

            log.info("risk.generate_exit_orders.success", extra={"extra": {"symbol": symbol, "tp_price": take_profit_price, "sl_price": stop_loss_price}})
            return {"take_profit": tp_order, "stop_loss": sl_order}

        except Exception:
            log.error("risk.generate_exit_orders.fail", exc_info=True)
            return None

    def _get_account_info(self) -> Optional[Account]:
        """DEPRECATED: Use portfolio_manager.account directly."""
        log.warning("risk._get_account_info.deprecated")
        return self.portfolio_manager.account

    def _get_positions(self) -> List[Position]:
        """DEPRECATED: Use portfolio_manager.positions directly."""
        log.warning("risk._get_positions.deprecated")
        return list(self.portfolio_manager.positions.values())

    def _check_volatility_for_symbol(self, symbol: str, data: pd.DataFrame, interval: str) -> bool:
        """Checks if the volatility for a symbol exceeds the circuit breaker threshold."""
        multiplier = self.config.circuit_breaker_atr_multiplier
        if not multiplier or multiplier <= 0:
            return False # Circuit breaker is disabled

        # The data is now passed in, so we don't need to fetch it.
        if data is None or data.empty:
            log.warning("risk.volatility_check.no_data", extra={"extra": {"symbol": symbol, "reason": "No data provided for volatility check."}})
            return False # Cannot perform check

        # Ensure data is sorted by time
        data = data.sort_index()

        # Calculate ATR for the series, excluding the most recent bar
        # Ensure we have enough data for the ATR calculation window
        atr_window = 14 # A common setting for ATR
        if len(data) < atr_window + 2:
            log.warning("risk.volatility_check.no_data", extra={"extra": {"symbol": symbol, "reason": "Not enough data for ATR calculation."}})
            return False

        historical_atr = atr(data['high'].iloc[:-1], data['low'].iloc[:-1], data['close'].iloc[:-1], window=atr_window).iloc[-1]

        # Calculate the True Range of the most recent bar
        last_bar = data.iloc[-1]
        prev_close = data['close'].iloc[-2]
        true_range = max(
            last_bar['high'] - last_bar['low'],
            abs(last_bar['high'] - prev_close),
            abs(last_bar['low'] - prev_close)
        )

        if historical_atr <= 0: # Avoid division by zero or nonsensical checks
            return False

        # Check if the current true range exceeds the historical average by the multiplier
        is_tripped = true_range > historical_atr * multiplier
        log.info(
            "risk.volatility_check.evaluate",
            extra={
                "extra": {
                    "symbol": symbol,
                    "is_tripped": is_tripped,
                    "true_range": true_range,
                    "historical_atr": historical_atr,
                    "multiplier": multiplier,
                }
            },
        )
        if is_tripped:
            self.is_halted = True
            self.halt_reason = f"Volatility circuit breaker tripped for {symbol}. True Range ({true_range:.2f}) > ATR ({historical_atr:.2f}) * {multiplier}"
            log.critical("risk.halt.volatility_exceeded", extra={"extra": {"symbol": symbol, "true_range": true_range, "atr": historical_atr, "multiplier": multiplier}})
            return True

        return False

    def volatility_check(self, historical_data: pd.DataFrame, symbol: str) -> bool:
        """
        Checks if the current volatility is too high compared to the historical average.
        Returns True if the circuit breaker is tripped, False otherwise.
        """
        if self.config.circuit_breaker_atr_multiplier <= 0:
            return False # Disabled

        try:
            # Calculate the most recent True Range
            high = historical_data['high'].iloc[-1]
            low = historical_data['low'].iloc[-1]
            prev_close = historical_data['close'].iloc[-2]
            true_range = max(high - low, abs(high - prev_close), abs(low - prev_close))

            # Calculate the historical ATR
            historical_atr = ta.volatility.average_true_range(high=historical_data['high'], low=historical_data['low'], close=historical_data['close'], window=14).iloc[-1]

            # Check if the current true range exceeds the historical ATR by the multiplier
            is_tripped = true_range > (historical_atr * self.config.circuit_breaker_atr_multiplier)
            
            log.info("risk.volatility_check.evaluate", extra={"extra": {
                "symbol": symbol,
                "is_tripped": str(is_tripped),
                "true_range": true_range,
                "historical_atr": historical_atr,
                "multiplier": self.config.circuit_breaker_atr_multiplier
            }})
            
            return is_tripped
        except Exception:
            log.error("risk.volatility_check.fail", exc_info=True)
            return False # Fail safe, don't halt

    def check_for_halt(self, historical_data: Dict[str, pd.DataFrame], trade_interval: str) -> bool:
        """
        Checks all halt conditions. If any are met, sets the halt flag and returns True.
        If no conditions are met, it ensures the halt is lifted and returns False.
        """
        log.info("risk.check_for_halt.start")
        # --- Check for conditions that would CAUSE a halt ---

        # 1. Check for daily drawdown
        account = self.portfolio_manager.account
        if account:
            try:
                equity = account.equity
                last_equity = account.last_equity
                drawdown = (equity / last_equity) - 1 if last_equity > 0 else 0
                
                is_exceeded = drawdown < self.config.max_daily_drawdown_percent
                log.info(
                    "risk.check_for_halt.drawdown_check",
                    extra={
                        "extra": {
                            "is_exceeded": is_exceeded,
                            "drawdown": drawdown,
                            "max_drawdown": self.config.max_daily_drawdown_percent,
                        }
                    },
                )
                if is_exceeded:
                    self.is_halted = True
                    self.halt_reason = f"Max daily drawdown exceeded: {drawdown:.2%} < {self.config.max_daily_drawdown_percent:.2%}"
                    log.critical("risk.halt.drawdown_exceeded", extra={"extra": {"drawdown": drawdown, "max_drawdown": self.config.max_daily_drawdown_percent}})
                    return True # Halt immediately
            except (ValueError, ZeroDivisionError):
                log.error("risk.halt_check.drawdown_error", exc_info=True)
                self.is_halted = True
                self.halt_reason = "Could not calculate drawdown due to invalid account data."
                return True
        else:
            log.error("risk.halt_check.no_account", extra={"extra": {"reason": "Cannot check drawdown without account info"}})
            # In a fail-safe mode, we might halt if we can't get account info
            self.is_halted = True
            self.halt_reason = "Could not retrieve account information to verify drawdown."
            return True

        # 2. Check for volatility circuit breaker for each symbol in the watch list
        for symbol, data in historical_data.items():
            if self.volatility_check(data, symbol):
                self.is_halted = True
                self.halt_reason = f"Volatility circuit breaker tripped for {symbol}."
                log.critical("risk.check_for_halt.volatility_halt", extra={"extra": {"symbol": symbol}})
                return True # Halt immediately

        # --- If we've reached this point, no halt conditions were met ---
        if self.is_halted:
            log.info("risk.halt.reset", extra={"extra": {"reason": "All risk conditions are now normal."}})
            self.is_halted = False
            self.halt_reason = ""
        
        log.info("risk.check_for_halt.end", extra={"extra": {"is_halted": self.is_halted}})
        return self.is_halted
    
    def manage_open_positions(self, strategy: Strategy):
        """
        Manages open positions according to the defined strategy and risk rules.
        """
        log.info("risk.manage_open_positions.start")
        
        if self.is_halted:
            log.warning("risk.manage_open_positions.halted", extra={"extra": {"reason": self.halt_reason}})
            return # Do not manage positions if halted

        positions = list(self.portfolio_manager.positions.values())
        if not positions:
            log.info("risk.manage_open_positions.no_positions")
            return # No positions to manage

        for position in positions:
            symbol = position.symbol
            qty = position.qty
            market_value = position.market_value
            unrealized_pl = position.unrealized_pl

            log.info("risk.manage_open_positions.evaluating", extra={"extra": {"symbol": symbol, "qty": qty, "market_value": market_value, "unrealized_pl": unrealized_pl}})
            
            # Example rule: Close positions with high unrealized loss
            if unrealized_pl < -100: # Arbitrary threshold for example
                log.info("risk.manage_open_positions.closing_loss", extra={"extra": {"symbol": symbol, "unrealized_pl": unrealized_pl}})
                # Here we would place a market order to close the position
                # self.client.close_position(symbol)
            
            # Example rule: Reduce position size if too large
            if qty > 10: # Arbitrary max qty for example
                new_qty = qty / 2
                log.info("risk.manage_open_positions.reducing_size", extra={"extra": {"symbol": symbol, "old_qty": qty, "new_qty": new_qty}})
                # Here we would place a reduce-only order
                # self.client.reduce_position_size(symbol, new_qty)
        
        log.info("risk.manage_open_positions.end")

    def is_drawdown_exceeded(self, account_equity: float) -> bool:
        """
        Checks if the current drawdown exceeds the maximum allowed drawdown.
        """
        daily_pnl = get_daily_pnl()
        drawdown_percent = (daily_pnl / account_equity) * 100 if account_equity > 0 else 0
        if drawdown_percent < -self.config.max_daily_drawdown_percent:
            self.is_halted = True
            self.halt_reason = f"Account drawdown exceeded: {drawdown_percent:.2f}% < -{self.config.max_daily_drawdown_percent:.2f}%"
            log.critical("risk.halt.drawdown_exceeded", extra={"extra": {"drawdown_percent": drawdown_percent, "max_drawdown_percent": -self.config.max_daily_drawdown_percent}})
            return True
        
        return False
