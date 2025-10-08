"""
A mock broker for backtesting purposes that simulates order execution.
"""
import logging
from datetime import datetime
from smartcfd.broker import Broker, Order
import pandas as pd

log = logging.getLogger(__name__)

class MockBroker(Broker):
    """
    A simulated broker that processes orders instantly at the provided price
    and tracks them in memory.
    """
    def __init__(self, data: pd.DataFrame):
        self.orders = []
        self.next_order_id = 1
        self.data = data
        self.current_step = 0
        self.api_base = "https://paper-api.alpaca.markets"  # Mock attribute
        self.trade_count = 0
        self.trade_history = []

    def set_step(self, step: int):
        """Sets the current time step for the simulation."""
        self.current_step = step

    def submit_order(self, symbol: str, qty: float, side: str, order_type: str, time_in_force: str) -> Order | None:
        """
        Simulates submitting an order. The order is considered filled instantly
        at the current bar's closing price.
        """
        order_id = str(self.next_order_id)
        self.next_order_id += 1

        if self.current_step >= len(self.data):
            log.error("Broker step is out of data bounds.")
            return None
        current_price = self.data['close'].iloc[self.current_step]

        order = Order(
            id=order_id,
            symbol=symbol,
            qty=qty,
            side=side,
            status='filled',
            filled_qty=qty,
            filled_avg_price=current_price,
            created_at=datetime.utcnow()
        )
        self.orders.append(order)

        self.trade_count += 1
        self.trade_history.append({
            "timestamp": self.data.index[self.current_step],
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "price": current_price,
            "order_type": order_type
        })
        
        return order

    def get_trade_count(self) -> int:
        """
        Returns the total number of trades executed.
        """
        return self.trade_count

    def get_trade_history(self) -> pd.DataFrame:
        """
        Returns the trade history as a DataFrame.
        """
        return pd.DataFrame(self.trade_history)

    def get_account_info(self) -> dict:
        """
        Returns a mock account information dictionary.
        """
        # This is a mock implementation for backtesting.
        # It returns a static dictionary representing a healthy account.
        return {
            "id": "mock-account-id",
            "equity": "100000.0", # Represented as string like Alpaca API
            "last_equity": "100000.0",
            "buying_power": "200000.0",
            "cash": "100000.0",
            "status": "ACTIVE",
        }

    def list_positions(self) -> list:
        """
        Returns a list of mock positions. For this simple mock, we assume
        the portfolio object holds the state, so this can be empty.
        """
        # In a more complex backtester, this might reflect the state
        # of the BacktestPortfolio object.
        return []

    def get_order(self, order_id: str) -> Order | None:
        """
        Retrieves a simulated order by its ID.
        """
        for order in self.orders:
            if order.id == order_id:
                return order
        return None

    def list_orders(self, status: str = 'open', limit: int = 50) -> list[Order]:
        """
        Lists simulated orders. The 'status' filter is for API compatibility.
        """
        return [o for o in self.orders if o.status == status or status == 'all']

    def cancel_order(self, order_id: str) -> bool:
        """
        Simulates cancelling an order.
        """
        order = self.get_order(order_id)
        if order and order.status == 'open':
            order.status = 'canceled'
            return True
        return False
