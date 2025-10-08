import logging
import os
from typing import Any, List
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from .broker import Broker

log = logging.getLogger(__name__)

class AlpacaBroker(Broker):
    """
    A concrete implementation of the Broker interface for Alpaca.
    This class uses the official alpaca-trade-api-python SDK.
    """
    def __init__(self, api_key: str, secret_key: str, paper: bool = True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        if not self.api_key or not self.secret_key:
            log.error("Alpaca API key and secret key must be provided.")
            raise ValueError("Alpaca API key and secret key must be provided.")
        
        try:
            self.trading_client = TradingClient(
                self.api_key, self.secret_key, paper=self.paper
            )
            # Verify connection by fetching account info
            self.get_account_info()
            log.info("Alpaca TradingClient initialized and connection verified.")
        except Exception as e:
            log.error(f"Failed to initialize Alpaca TradingClient: {e}", exc_info=True)
            raise

    def get_account_info(self) -> Any:
        """Retrieves account information from the broker."""
        log.debug("Fetching Alpaca account info.")
        try:
            account = self.trading_client.get_account()
            log.info(f"Successfully fetched account info for account {account.account_number}.")
            return account
        except Exception as e:
            log.error(f"Failed to fetch Alpaca account info: {e}", exc_info=True)
            raise

    def list_positions(self) -> List[Any]:
        """Retrieves a list of current positions from the broker."""
        log.debug("Fetching Alpaca positions.")
        try:
            positions = self.trading_client.get_all_positions()
            log.info(f"Successfully fetched {len(positions)} open positions.")
            return positions
        except Exception as e:
            log.error(f"Failed to fetch Alpaca positions: {e}", exc_info=True)
            raise

    def get_orders(self, status: str = 'open') -> List[Any]:
        """Retrieves a list of orders from the broker."""
        log.debug(f"Fetching Alpaca orders with status: {status}")
        try:
            if status == 'open':
                order_status = QueryOrderStatus.OPEN
            else:
                order_status = QueryOrderStatus.ALL

            order_request = GetOrdersRequest(status=order_status)
            orders = self.trading_client.get_orders(filter=order_request)
            log.info(f"Successfully fetched {len(orders)} orders with status '{status}'.")
            return orders
        except Exception as e:
            log.error(f"Failed to fetch Alpaca orders: {e}", exc_info=True)
            raise

    def submit_order(self, symbol: str, qty: float, side: str, order_type: str, time_in_force: str) -> Any:
        """Submits an order to the broker."""
        log.info(f"Submitting order: {side} {qty} {symbol} ({order_type}, {time_in_force})")
        try:
            market_order_data = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide[side.upper()],
                time_in_force=TimeInForce[time_in_force.upper()]
            )
            market_order = self.trading_client.submit_order(order_data=market_order_data)
            log.info(f"Successfully submitted order {market_order.id} for {symbol}.")
            return market_order
        except Exception as e:
            log.error(f"Failed to submit order for {symbol}: {e}", exc_info=True)
            raise

    def close_position(self, symbol: str) -> Any:
        """Closes an open position for a given symbol."""
        log.info(f"Closing position for {symbol}.")
        try:
            # The SDK's close_position can return a list of orders or a single order
            # depending on the version and context. We'll handle both.
            result = self.trading_client.close_position(symbol)
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
