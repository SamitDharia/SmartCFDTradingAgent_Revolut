from abc import ABC, abstractmethod
from typing import List, Any
from .types import Order, OrderRequest

class Broker(ABC):
    """
    Abstract base class for a broker.
    Defines the interface for submitting orders and retrieving account information.
    """

    @abstractmethod
    def submit_order(self, order_request: OrderRequest) -> Any:
        """
        Submits an order to the broker.
        """
        pass

    @abstractmethod
    def get_account_info(self) -> Any:
        """
        Retrieves account information from the broker.
        """
        pass

    @abstractmethod
    def list_positions(self) -> List[Any]:
        """
        Retrieves a list of current positions from the broker.
        """
        pass

    @abstractmethod
    def close_position(self, symbol: str) -> Any:
        """
        Closes an open position for a given symbol.
        """
        pass

    # Optional convenience methods commonly used by Portfolio/Trader
    def get_orders(self, status: str = 'open') -> List[Any]:
        """Retrieves a list of orders from the broker."""
        raise NotImplementedError

    def get_order_by_client_id(self, client_order_id: str) -> Any:
        """Retrieves a single order by its client order ID."""
        raise NotImplementedError

    def submit_take_profit_order(self, symbol: str, qty: str, side: str, price: str, client_order_id: str) -> Any:
        """Submits a take-profit order (limit)."""
        raise NotImplementedError

    def submit_stop_loss_order(self, symbol: str, qty: str, side: str, price: str, client_order_id: str) -> Any:
        """Submits a stop-loss order (stop)."""
        raise NotImplementedError

    def replace_order(self, order_id: str, qty: str | None = None, limit_price: str | None = None, stop_price: str | None = None) -> Any:
        """Replaces an existing order (e.g., adjust quantity or price)."""
        raise NotImplementedError
