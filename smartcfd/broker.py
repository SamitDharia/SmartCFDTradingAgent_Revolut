from abc import ABC, abstractmethod
from typing import List, Dict, Any

class Broker(ABC):
    """
    Abstract base class for a broker.
    Defines the interface for submitting orders and retrieving account information.
    """

    @abstractmethod
    def submit_order(self, symbol: str, qty: float, side: str, order_type: str, time_in_force: str) -> Dict[str, Any]:
        """
        Submits an order to the broker.
        """
        pass

    @abstractmethod
    def get_account_info(self) -> Dict[str, Any]:
        """
        Retrieves account information from the broker.
        """
        pass

    @abstractmethod
    def list_positions(self) -> List[Dict[str, Any]]:
        """
        Retrieves a list of current positions from the broker.
        """
        pass


from .alpaca_client import AlpacaClient

class AlpacaBroker(Broker):
    """
    A concrete implementation of the Broker interface for Alpaca.
    """

    def __init__(self, client: AlpacaClient):
        self.client = client

    def submit_order(self, symbol: str, qty: float, side: str, order_type: str, time_in_force: str) -> Dict[str, Any]:
        """
        Submits an order to the Alpaca API.
        """
        return self.client.submit_order(symbol, qty, side, order_type, time_in_force)

    def get_account_info(self) -> Dict[str, Any]:
        """
        Retrieves account information from the Alpaca API.
        """
        return self.client.get_account()

    def list_positions(self) -> List[Dict[str, Any]]:
        """
        Retrieves a list of current positions from the Alpaca API.
        """
        return self.client.get_positions()
