import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from smartcfd.alpaca_client import AlpacaClient, OrderRequest
from smartcfd.config import RiskConfig
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
    def __init__(self, client: AlpacaClient, config: RiskConfig):
        self.client = client
        self.config = config
        self.is_halted = False

    def calculate_order_qty(self, symbol: str, side: str) -> float:
        """
        Calculates the quantity for an order based on a fixed risk percentage.
        """
        log.info("risk.calculate_order_qty.start", extra={"extra": {"symbol": symbol, "side": side}})

        if self.is_halted:
            log.warning("risk.calculate_order_qty.halted", extra={"extra": {"reason": "Trading is halted, returning 0 qty."}})
            return 0.0

        account = self._get_account_info()
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
            r = self.client.session.get(f"{self.client.api_base}/v2/account")
            r.raise_for_status()
            return Account.model_validate(r.json())
        except Exception as e:
            log.error("risk.account_info.fail", extra={"extra": {"error": repr(e)}})
            return None

    def _get_positions(self) -> List[Position]:
        """Fetches and validates the current open positions."""
        try:
            r = self.client.session.get(f"{self.client.api_base}/v2/positions")
            r.raise_for_status()
            return [Position.model_validate(p) for p in r.json()]
        except Exception as e:
            log.error("risk.positions.fail", extra={"extra": {"error": repr(e)}})
            return []

    def check_for_halt(self) -> bool:
        """
        Checks if the max daily drawdown has been exceeded. If so, halts trading.
        Drawdown is a negative value, so we check if it's *less than* the configured max.
        e.g., if drawdown is -6% and limit is -5%, trading should halt.
        """
        if self.is_halted:
            log.warning("risk.check.halted", extra={"extra": {"reason": "already halted"}})
            return True

        account = self._get_account_info()
        if not account:
            log.error("risk.halt_check.no_account", extra={"extra": {"reason": "Cannot check drawdown without account info"}})
            # Fail safe: if we can't get account info, halt trading
            self.is_halted = True
            return True

        equity = float(account.equity)
        last_equity = float(account.last_equity)
        
        if last_equity == 0: # Avoid division by zero on new accounts
            return False

        drawdown_percent = ((equity - last_equity) / last_equity) * 100.0

        # max_daily_drawdown_percent is negative, e.g., -5.0
        if drawdown_percent < self.config.max_daily_drawdown_percent:
            log.critical("risk.halt.drawdown_exceeded", extra={"extra": {"drawdown_percent": round(drawdown_percent, 2), "limit_percent": self.config.max_daily_drawdown_percent}})
            self.is_halted = True
            return True
        
        return False

    def filter_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filters a list of proposed actions based on risk rules.
        - Max Position Size: No single position can exceed this notional value.
        - Max Total Exposure: The sum of all position market values cannot exceed this.
        """
        if self.is_halted:
            log.warning("risk.filter.halted", extra={"extra": {"reason": "Trading is halted, no actions will be approved."}})
            return []

        positions = self._get_positions()
        current_exposure = sum(float(p.market_value) for p in positions)
        
        approved_actions = []
        for action in actions:
            # We only apply these risk rules to opening new positions
            if action.get("action") == "buy":
                try:
                    order = OrderRequest.model_validate(action.get("order_details", {}))
                except Exception as e:
                    log.error("risk.filter.invalid_order", extra={"extra": {"action": action, "error": repr(e)}})
                    continue

                # This is a simplification. A robust implementation would fetch the current
                # market price to calculate the notional value. For now, we assume a fixed price.
                # This is a known limitation for this implementation phase.
                notional_value = float(order.qty) * 150.0 # Placeholder average price

                # Rule 1: Check against max position size
                if notional_value > self.config.max_position_size:
                    log.warning("risk.filter.reject", extra={"extra": {"symbol": order.symbol, "reason": "exceeds_max_position_size", "notional": notional_value, "limit": self.config.max_position_size}})
                    continue
                
                # Rule 2: Check against max total exposure
                if (current_exposure + notional_value) > self.config.max_total_exposure:
                    log.warning("risk.filter.reject", extra={"extra": {"symbol": order.symbol, "reason": "exceeds_max_total_exposure", "new_exposure": current_exposure + notional_value, "limit": self.config.max_total_exposure}})
                    continue
                
                # If approved, add the notional value to our running total for this session
                current_exposure += notional_value

            approved_actions.append(action)
            
        log.info("risk.filter.end", extra={"extra": {"approved_count": len(approved_actions), "initial_count": len(actions)}})
        return approved_actions
