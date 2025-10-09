import logging
import os
from typing import Any, List
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    GetOrdersRequest,
    BracketOrderRequest,
    StopLossRequest,
    TakeProfitRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.common.exceptions import APIError
from .broker import Broker
from .types import OrderRequest

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
        try:
            account = self.trading_client.get_account()
            log.info(f"Successfully fetched account info for account {account.account_number}.")
            return account
        except Exception as e:
            log.error(f"Failed to fetch Alpaca account info: {e}", exc_info=True)
            raise

    def list_positions(self) -> List[Any]:
        """Retrieves a list of current positions from the broker."""
        try:
            positions = self.trading_client.get_all_positions()
            log.info(f"Successfully fetched {len(positions)} open positions.")
            return positions
        except Exception as e:
            log.error(f"Failed to fetch Alpaca positions: {e}", exc_info=True)
            raise

    def get_orders(self, status: str = 'open') -> List[Any]:
        """Retrieves a list of orders from the broker."""
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

    def submit_order(self, order_request: OrderRequest) -> Any:
        """Submits a bracket order."""
        try:
            # Convert our internal OrderRequest to the Alpaca SDK's BracketOrderRequest
            bracket_order_data = BracketOrderRequest(
                symbol=order_request.symbol,
                qty=float(order_request.qty),
                side=OrderSide[order_request.side.upper()],
                time_in_force=TimeInForce[order_request.time_in_force.upper()],
                order_class=order_request.order_class,
                take_profit=TakeProfitRequest(
                    limit_price=float(order_request.take_profit["limit_price"])
                ),
                stop_loss=StopLossRequest(
                    stop_price=float(order_request.stop_loss["stop_price"])
                ),
            )

            log.info("alpaca.submit_order.request", extra={"extra": bracket_order_data.model_dump()})

            submitted_order = self.trading_client.submit_order(order_data=bracket_order_data)

            log.info("alpaca.submit_order.success", extra={"extra": {"order_id": submitted_order.id}})
            return submitted_order
        except APIError as e:
            log.error("alpaca.submit_order.fail", exc_info=True)
            raise

    def close_position(self, symbol: str) -> Any:
        """Closes an open position for a given symbol."""
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
