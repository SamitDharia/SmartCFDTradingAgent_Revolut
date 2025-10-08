import logging
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from smartcfd.alpaca_client import AlpacaClient, OrderResponse

log = logging.getLogger(__name__)


# --- Pydantic Models for Broker State ---

class Account(BaseModel):
    """A standardized model for account information."""
    id: str
    equity: float
    last_equity: float
    buying_power: float
    cash: float
    status: str
    is_online: bool = Field(default=True)


class Position(BaseModel):
    """A standardized model for an open position."""
    symbol: str
    qty: float
    side: str # 'long' or 'short'
    market_value: float
    unrealized_pl: float
    unrealized_plpc: float  # Unrealized profit/loss percentage
    avg_entry_price: float


class PortfolioManager:
    """
    Manages the state of the trading account, including account details,
    open positions, and pending orders.
    """
    def __init__(self, client: AlpacaClient):
        self.client = client
        self.account: Optional[Account] = None
        self.positions: Dict[str, Position] = {}
        self.orders: List[OrderResponse] = []

    def reconcile(self):
        """
        Fetches the latest state from the broker and updates the portfolio.
        This should be called at the start of each trading cycle.
        """
        log.info("portfolio.reconcile.start")
        try:
            # 1. Fetch Account Details
            account_data = self.client.get_account()
            if account_data:
                self.account = Account(
                    id=account_data['id'],
                    equity=float(account_data['equity']),
                    last_equity=float(account_data['last_equity']),
                    buying_power=float(account_data['buying_power']),
                    cash=float(account_data['cash']),
                    status=account_data['status'],
                )
                log.info("portfolio.reconcile.account_updated", extra={"extra": self.account.model_dump()})
            else:
                self.account = None
                log.warning("portfolio.reconcile.no_account_data")

            # 2. Fetch Open Positions
            positions_data = self.client.get_positions()
            self.positions.clear()
            for pos_obj in positions_data:
                position = Position(
                    symbol=pos_obj['symbol'],
                    qty=float(pos_obj['qty']),
                    side=pos_obj['side'],
                    market_value=float(pos_obj['market_value']),
                    unrealized_pl=float(pos_obj['unrealized_pl']),
                    unrealized_plpc=float(pos_obj['unrealized_plpc']),
                    avg_entry_price=float(pos_obj['avg_entry_price']),
                )
                self.positions[pos_obj['symbol']] = position
            log.info("portfolio.reconcile.positions_updated", extra={"extra": {"position_count": len(self.positions)}})

            # 3. Fetch Open/Pending Orders
            self.orders = self.client.get_orders(status="open")
            log.info("portfolio.reconcile.orders_updated", extra={"extra": {"order_count": len(self.orders)}})

            log.info("portfolio.reconcile.end")

        except Exception:
            log.error("portfolio.reconcile.fail", exc_info=True)
            # In case of failure, mark the portfolio as potentially offline/stale
            if self.account:
                self.account.is_online = False

    def get_position(self, symbol: str) -> Optional[Position]:
        """Returns the position for a given symbol, if it exists."""
        return self.positions.get(symbol)

    def has_open_position(self, symbol: str) -> bool:
        """Checks if there is an open position for a given symbol."""
        return symbol in self.positions

    def has_pending_order(self, symbol: str) -> bool:
        """Checks if there are any pending (open) orders for a given symbol."""
        return any(order.symbol == symbol for order in self.orders)

    def get_total_exposure(self) -> float:
        """Calculates the total market value of all open positions."""
        if not self.positions:
            return 0.0
        return sum(pos.market_value for pos in self.positions.values())

    def get_exposure_for_symbol(self, symbol: str) -> float:
        """Returns the market value for a specific symbol's position."""
        position = self.get_position(symbol)
        return position.market_value if position else 0.0
