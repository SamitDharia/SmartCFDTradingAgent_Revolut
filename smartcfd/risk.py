import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from smartcfd.alpaca_client import AlpacaClient, OrderRequest
from smartcfd.config import RiskConfig

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
        drawdown = (last_equity - equity) / last_equity

        if drawdown > self.config.max_daily_drawdown_percent:
            log.critical("risk.halt.drawdown_exceeded", extra={"extra": {"drawdown": drawdown, "limit": self.config.max_daily_drawdown_percent}})
            self.is_halted = True
            return True
        
        return False

    def filter_actions(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filters a list of proposed actions based on risk rules.
        """
        if self.is_halted:
            log.warning("risk.filter.halted", extra={"extra": {"reason": "Trading is halted"}})
            return []

        # In a real implementation, we would check each proposed order against
        # position size limits, total exposure, etc.
        # For now, we'll just log and pass them through.
        
        log.info("risk.filter.start", extra={"extra": {"action_count": len(actions)}})
        
        approved_actions = []
        for action in actions:
            if action.get("action") == "buy":
                # Example: Check if this buy order would exceed max position size
                # order = OrderRequest(**action.get("order_details"))
                # if self._would_exceed_limits(order):
                #     log.warning("risk.filter.reject", extra={"extra": {"order": order.model_dump(), "reason": "exceeds_limit"}})
                #     continue
                pass
            approved_actions.append(action)
            
        log.info("risk.filter.end", extra={"extra": {"approved_count": len(approved_actions)}})
        return approved_actions
