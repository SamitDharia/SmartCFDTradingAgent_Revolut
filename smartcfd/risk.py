import logging
from typing import List, Dict, Any, Optional
import pandas as pd
from pydantic import BaseModel

from smartcfd.alpaca_client import AlpacaClient, OrderRequest
from smartcfd.config import RiskConfig
from smartcfd.data_loader import DataLoader
from smartcfd.indicators import atr
from smartcfd.strategy import Strategy

log = logging.getLogger("risk")

# --- Pydantic Models for Alpaca Data ---

class Position(BaseModel):
    """A model for an open position from the Alpaca API."""
    symbol: str
    qty: str
    market_value: str
    unrealized_pl: str

class Account(BaseModel):
    """A model for account information from the Alpaca API."""
    equity: str
    last_equity: str # Equity at the end of the last trading day
    buying_power: str

class RiskManager:
    """
    Manages and enforces risk rules for trading.
    """
    def __init__(self, client: AlpacaClient, data_loader: DataLoader, config: RiskConfig):
        self.client = client
        self.data_loader = data_loader
        self.config = config
        self.is_halted = False
        self.halt_reason = ""

    def calculate_order_qty(self, symbol: str, side: str) -> float:
        """
        Calculates the quantity for an order based on a fixed risk percentage.
        """
        log.info("risk.calculate_order_qty.start", extra={"extra": {"symbol": symbol, "side": side}})

        if self.is_halted:
            log.warning("risk.calculate_order_qty.halted", extra={"extra": {"reason": self.halt_reason, "symbol": symbol}})
            return 0.0

        account = self.client.get_account()
        if not account:
            log.error("risk.calculate_order_qty.no_account", extra={"extra": {"reason": "Cannot calculate quantity without account info."}})
            return 0.0

        try:
            equity = float(account.equity)
            
            # For this simple implementation, we risk a fixed percentage of equity on each trade.
            risk_amount = equity * self.config.risk_per_trade_percent
            
            # To calculate quantity, we need the price.
            # We'll fetch the latest trade for the symbol.
            latest_trade = self.client.get_latest_crypto_trade(symbol)
            if not latest_trade:
                log.error("risk.calculate_order_qty.no_price", extra={"extra": {"symbol": symbol}})
                return 0.0
            
            price = latest_trade['trade']['p']
            
            if price <= 0:
                log.error("risk.calculate_order_qty.invalid_price", extra={"extra": {"symbol": symbol, "price": price}})
                return 0.0

            # Simple quantity calculation
            qty = risk_amount / price
            
            log.info("risk.calculate_order_qty.success", extra={"extra": {"symbol": symbol, "equity": equity, "risk_amount": risk_amount, "price": price, "calculated_qty": qty}})
            
            # Here we could add checks against max_position_size etc., but for now we keep it simple.
            # Also, Alpaca requires notional orders for crypto to be >= $1.
            if (qty * price) < 1.0:
                log.warning("risk.calculate_order_qty.too_small", extra={"extra": {"symbol": symbol, "notional_value": qty * price}})
                return 0.0

            return round(qty, 8) # Return a reasonable precision for crypto

        except Exception as e:
            log.error("risk.calculate_order_qty.fail", extra={"extra": {"error": repr(e)}})
            return 0.0

    def _get_account_info(self) -> Optional[Account]:
        """Fetches and validates the current account state."""
        try:
            account_data = self.client.get_account()
            if account_data:
                return Account.model_validate(account_data.model_dump())
            return None
        except Exception as e:
            log.error("risk.account_info.fail", extra={"extra": {"error": repr(e)}})
            return None

    def _get_positions(self) -> List[Position]:
        """Fetches and validates the current open positions."""
        try:
            positions_data = self.client.get_positions()
            if positions_data:
                return [Position.model_validate(p.model_dump()) for p in positions_data]
            return []
        except Exception as e:
            log.error("risk.positions.fail", extra={"extra": {"error": repr(e)}})
            return []

    def _check_volatility_for_symbol(self, symbol: str, interval: str) -> bool:
        """Checks if the volatility for a symbol exceeds the circuit breaker threshold."""
        multiplier = self.config.circuit_breaker_atr_multiplier
        if not multiplier or multiplier <= 0:
            return False # Circuit breaker is disabled

        # Fetch recent data to calculate ATR. We need enough for the ATR window + 1 for previous close.
        data = self.data_loader.get_market_data([symbol], interval, limit=50)
        if data is None or data.empty or len(data) < 2:
            log.warning("risk.volatility_check.no_data", extra={"extra": {"symbol": symbol, "reason": "Not enough data for volatility check."}})
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
        if true_range > historical_atr * multiplier:
            self.is_halted = True
            self.halt_reason = f"Volatility circuit breaker tripped for {symbol}. True Range ({true_range:.2f}) > ATR ({historical_atr:.2f}) * {multiplier}"
            log.critical("risk.halt.volatility_exceeded", extra={"extra": {"symbol": symbol, "true_range": true_range, "atr": historical_atr, "multiplier": multiplier}})
            return True

        return False

    def check_for_halt(self, watch_list: List[str], interval: str) -> bool:
        """
        Checks all halt conditions. If any are met, sets the halt flag and returns True.
        If no conditions are met, it ensures the halt is lifted and returns False.
        """
        # --- Check for conditions that would CAUSE a halt ---

        # 1. Check for daily drawdown
        account = self._get_account_info()
        if account:
            try:
                equity = float(account.equity)
                last_equity = float(account.last_equity)
                drawdown = (equity / last_equity) - 1
                
                if drawdown < self.config.max_daily_drawdown_percent:
                    self.is_halted = True
                    self.halt_reason = f"Max daily drawdown exceeded: {drawdown:.2%} < {self.config.max_daily_drawdown_percent:.2%}"
                    log.critical("risk.halt.drawdown_exceeded", extra={"extra": {"drawdown": drawdown, "max_drawdown": self.config.max_daily_drawdown_percent}})
                    return True # Halt immediately
            except (ValueError, ZeroDivisionError) as e:
                log.error("risk.halt_check.drawdown_error", extra={"extra": {"error": repr(e)}})
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
        for symbol in watch_list:
            if self._check_volatility_for_symbol(symbol, interval):
                self.is_halted = True # The reason is set inside the check
                return True # Halt immediately

        # --- If we've reached this point, no halt conditions were met ---
        if self.is_halted:
            log.info("risk.halt.reset", extra={"extra": {"reason": "All risk conditions are now normal."}})
            self.is_halted = False
            self.halt_reason = ""
        
        return self.is_halted
    
    def manage_open_positions(self, strategy: Strategy):
        """
        Manages open positions according to the defined strategy and risk rules.
        """
        log.info("risk.manage_open_positions.start", extra={"extra": {}})
        
        if self.is_halted:
            log.warning("risk.manage_open_positions.halted", extra={"extra": {"reason": self.halt_reason}})
            return # Do not manage positions if halted

        positions = self._get_positions()
        if not positions:
            log.info("risk.manage_open_positions.no_positions", extra={"extra": {}})
            return # No positions to manage

        for position in positions:
            symbol = position.symbol
            qty = float(position.qty)
            market_value = float(position.market_value)
            unrealized_pl = float(position.unrealized_pl)

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
        
        log.info("risk.manage_open_positions.end", extra={"extra": {}})
