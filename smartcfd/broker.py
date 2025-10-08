from abc import ABC, abstractmethod
from typing import List, Any
from .types import Order

class Broker(ABC):
    """
    Abstract base class for a broker.
    Defines the interface for submitting orders and retrieving account information.
    """

    @abstractmethod
    def submit_order(self, symbol: str, qty: float, side: str, order_type: str, time_in_force: str) -> Any:
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