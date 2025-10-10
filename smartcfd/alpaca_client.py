import logging
from typing import Any, List
import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import APIError
from .broker import Broker
from .types import OrderRequest

log = logging.getLogger(__name__)

class AlpacaBroker(Broker):
    """
    A concrete implementation of the Broker interface for Alpaca.
    This class uses the official alpaca-trade-api-python SDK.
    """
    def __init__(self, key_id: str, secret_key: str, paper: bool = True):
        self.api_key = key_id
        self.secret_key = secret_key
        self.paper = paper
        self.base_url = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
        
        if not self.api_key or not self.secret_key:
            log.error("Alpaca API key and secret key must be provided.")
            raise ValueError("Alpaca API key and secret key must be provided.")
        
        try:
            self.api = tradeapi.REST(
                self.api_key, self.secret_key, base_url=self.base_url, api_version='v2'
            )
            # Verify connection by fetching account info
            self.get_account_info()
            log.info("Alpaca TradingClient initialized and connection verified.")
        except Exception as e:
            log.error(f"Failed to initialize Alpaca TradingClient: {e}", exc_info=True)
            raise

    def get_account_info(self) -> Any:
        """Retrieves account information from the broker."""
        try:
            account = self.api.get_account()
            log.info(f"Successfully fetched account info for account {account.account_number}.")
            return account
        except Exception as e:
            log.error(f"Failed to fetch Alpaca account info: {e}", exc_info=True)
            raise

    def list_positions(self) -> List[Any]:
        """Retrieves a list of current positions from the broker."""
        try:
            positions = self.api.list_positions()
            log.info(f"Successfully fetched {len(positions)} open positions.")
            return positions
        except Exception as e:
            log.error(f"Failed to fetch Alpaca positions: {e}", exc_info=True)
            raise

    def get_orders(self, status: str = 'open') -> List[Any]:
        """Retrieves a list of orders from the broker."""
        try:
            orders = self.api.list_orders(status=status)
            log.info(f"Successfully fetched {len(orders)} orders with status '{status}'.")
            return orders
        except Exception as e:
            log.error(f"Failed to fetch Alpaca orders: {e}", exc_info=True)
            raise

    def submit_order(self, order_request: OrderRequest) -> Any:
        """Submits a simple market order."""
        try:
            # For crypto, we only submit a simple market order.
            # The SL/TP logic is handled by a subsequent OCO order.
            order_data = {
                "symbol": order_request.symbol,
                "qty": order_request.qty,
                "side": order_request.side,
                "type": "market",
                "time_in_force": "gtc",
                "client_order_id": order_request.client_order_id,
            }
            submitted_order = self.api.submit_order(**order_data)
            log.info("alpaca.submit_order.success", extra={"extra": {"order_id": submitted_order.id}})
            return submitted_order
        except APIError as e:
            log.error("alpaca.submit_order.fail", exc_info=True)
            raise

    def submit_take_profit_order(self, symbol: str, qty: str, side: str, price: str, client_order_id: str) -> Any:
        """Submits a take-profit (limit) order."""
        try:
            order_data = {
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "type": "limit",
                "time_in_force": "gtc",
                "limit_price": price,
                "client_order_id": client_order_id,
            }
            submitted_order = self.api.submit_order(**order_data)
            log.info("alpaca.submit_take_profit.success", extra={"extra": {"order_id": submitted_order.id}})
            return submitted_order
        except APIError as e:
            log.error("alpaca.submit_take_profit.fail", exc_info=True)
            raise

    def submit_stop_loss_order(self, symbol: str, qty: str, side: str, price: str, client_order_id: str) -> Any:
        """Submits a stop-loss (stop) order."""
        try:
            order_data = {
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "type": "stop",
                "time_in_force": "gtc",
                "stop_price": price,
                "client_order_id": client_order_id,
            }
            submitted_order = self.api.submit_order(**order_data)
            log.info("alpaca.submit_stop_loss.success", extra={"extra": {"order_id": submitted_order.id}})
            return submitted_order
        except APIError as e:
            log.error("alpaca.submit_stop_loss.fail", exc_info=True)
            raise

    def get_order_by_client_id(self, client_order_id: str) -> Any:
        """Retrieves a single order by its client_order_id."""
        try:
            order = self.api.get_order_by_client_order_id(client_order_id)
            log.info("alpaca.get_order_by_client_id.success", extra={"extra": {"client_order_id": client_order_id}})
            return order
        except APIError as e:
            if e.code == 404:
                log.warning("alpaca.get_order_by_client_id.not_found", extra={"extra": {"client_order_id": client_order_id}})
                return None
            log.error("alpaca.get_order_by_client_id.fail", exc_info=True)
            raise

    def cancel_order(self, order_id: str) -> Any:
        """Cancels an open order."""
        try:
            self.api.cancel_order(order_id)
            log.info("alpaca.cancel_order.success", extra={"extra": {"order_id": order_id}})
        except APIError as e:
            log.error("alpaca.cancel_order.fail", exc_info=True)
            raise

    def close_position(self, symbol: str) -> Any:
        """Closes an open position for a given symbol."""
        try:
            result = self.api.close_position(symbol)
            if isinstance(result, list) and result:
                closed_order = result[0] # Typically one order is returned
                log.info(f"Successfully submitted request to close position for {symbol}. Order ID: {closed_order.id}")
                return closed_order
            elif not isinstance(result, list):
                 log.info(f"Successfully submitted request to close position for {symbol}. Order ID: {result.id}")
                 return result
            
            log.warning(f"Close position for {symbol} did not return an order. It might have already been closed.")
            return None
        except Exception as e:
            log.error(f"Failed to close position for {symbol}: {e}", exc_info=True)
            raise
