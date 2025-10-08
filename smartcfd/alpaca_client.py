import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Literal, Optional
from pydantic import BaseModel, Field

log = logging.getLogger("alpaca_client")

# --- Typed Models for Alpaca Orders API ---

class OrderRequest(BaseModel):
    """
    A model for submitting a new order to Alpaca.
    See: https://docs.alpaca.markets/reference/postorder
    """
    symbol: str
    qty: str
    side: Literal["buy", "sell"]
    type: Literal["market", "limit", "stop", "stop_limit", "trailing_stop"]
    time_in_force: Literal["day", "gtc", "opg", "cls", "ioc", "fok"]
    limit_price: Optional[str] = None
    stop_price: Optional[str] = None
    trail_price: Optional[str] = None
    trail_percent: Optional[str] = None
    extended_hours: Optional[bool] = None
    client_order_id: Optional[str] = None
    order_class: Optional[Literal["simple", "bracket", "oco", "oto"]] = None
    take_profit: Optional[dict] = None
    stop_loss: Optional[dict] = None

class TakeProfitRequest(BaseModel):
    """Defines a take profit order."""
    limit_price: str

class StopLossRequest(BaseModel):
    """Defines a stop loss order."""
    stop_price: str
    limit_price: Optional[str] = None


class OrderResponse(BaseModel):
    """
    A model for the response received after submitting an order.
    """
    id: str
    client_order_id: str
    created_at: str
    updated_at: str
    submitted_at: str
    filled_at: Optional[str] = None
    expired_at: Optional[str] = None
    canceled_at: Optional[str] = None
    failed_at: Optional[str] = None
    replaced_at: Optional[str] = None
    replaced_by: Optional[str] = None
    replaces: Optional[str] = None
    asset_id: str
    symbol: str
    asset_class: str
    notional: Optional[str] = None
    qty: str
    filled_qty: str
    filled_avg_price: Optional[str] = None
    order_class: str
    order_type: str = Field(alias='type')
    side: str
    time_in_force: str
    limit_price: Optional[str] = None
    stop_price: Optional[str] = None
    status: str
    extended_hours: bool
    legs: Optional[list] = None
    trail_price: Optional[str] = None
    trail_percent: Optional[str] = None
    hwm: Optional[str] = None

    model_config = {
        "populate_by_name": True
    }

class AlpacaClient:
    def __init__(self, api_base: str, session: requests.Session):
        self.api_base = api_base
        self.session = session

    def get_latest_crypto_trade(self, symbol: str) -> Optional[dict]:
        """
        Fetches the latest trade for a given crypto symbol.
        """
        url = f"{self.api_base.replace('api.', 'data.')}/v1beta3/crypto/us/latest/trades"
        params = {"symbols": symbol}
        log.info("alpaca.get_latest_crypto_trade.start", extra={"extra": {"symbol": symbol}})
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if symbol in data.get("trades", {}):
                log.info("alpaca.get_latest_crypto_trade.success", extra={"extra": {"symbol": symbol}})
                return data["trades"][symbol]
            log.warning("alpaca.get_latest_crypto_trade.no_trade_in_response", extra={"extra": {"symbol": symbol}})
            return None
        except requests.RequestException:
            log.error(
                "alpaca.get_latest_crypto_trade.fail",
                extra={"extra": {"symbol": symbol}},
                exc_info=True
            )
            return None

    def post_order(self, order_data: OrderRequest) -> OrderResponse:
        """
        Posts an order to the Alpaca API.
        
        Raises:
            requests.HTTPError: If the API returns a non-2xx status code after retries.
        """
        url = f"{self.api_base}/v2/orders"
        order_json = order_data.model_dump(by_alias=True)
        log.info("alpaca.post_order.start", extra={"extra": {"order": order_json}})
        try:
            # Use by_alias to correctly serialize 'type' to 'order_type'
            response = self.session.post(url, json=order_json)
            response.raise_for_status()
            order_response = OrderResponse.model_validate(response.json())
            log.info("alpaca.post_order.success", extra={"extra": {"order_response": order_response.model_dump()}})
            return order_response
        except requests.RequestException:
            log.error(
                "alpaca.post_order.fail", 
                extra={"extra": {"order": order_json}},
                exc_info=True
            )
            raise
        except Exception:
            log.error(
                "alpaca.post_order.parse_fail", 
                exc_info=True
            )
            raise

    def get_orders(self, status: str = "all", limit: int = 100, nested: bool = True) -> list[OrderResponse]:
        """
        Fetches a list of orders from the Alpaca API.
        """
        url = f"{self.api_base}/v2/orders"
        params = {
            "status": status,
            "limit": limit,
            "nested": nested,
        }
        log.info("alpaca.get_orders.start", extra={"extra": {"params": params}})
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            orders_data = response.json()
            validated_orders = [OrderResponse.model_validate(order) for order in orders_data]
            log.info("alpaca.get_orders.success", extra={"extra": {"order_count": len(validated_orders)}})
            return validated_orders
        except requests.RequestException:
            log.error(
                "alpaca.get_orders.fail",
                exc_info=True
            )
            raise

    def get_account(self):
        """
        Fetches account information from Alpaca.
        """
        url = f"{self.api_base}/v2/account"
        log.info("alpaca.get_account.start")
        try:
            response = self.session.get(url)
            response.raise_for_status()
            log.info("alpaca.get_account.success")
            # The response is a Pydantic model from the alpaca-trade-api,
            # so we can return it directly.
            return response.json()
        except requests.RequestException:
            log.error("alpaca.get_account.fail", exc_info=True)
            return None

    def get_positions(self):
        """
        Fetches all open positions from Alpaca.
        """
        url = f"{self.api_base}/v2/positions"
        log.info("alpaca.get_positions.start")
        try:
            response = self.session.get(url)
            response.raise_for_status()
            log.info("alpaca.get_positions.success")
            return response.json()
        except requests.RequestException:
            log.error("alpaca.get_positions.fail", exc_info=True)
            return []

    def close_position(self, symbol: str, qty: Optional[str] = None):
        """
        Closes an entire position for a given symbol.
        If qty is specified, it will close that quantity. Otherwise, it closes the entire position.
        """
        url = f"{self.api_base}/v2/positions/{symbol}"
        params = {}
        if qty:
            params['qty'] = qty
            
        log.info("alpaca.close_position.start", extra={"extra": {"symbol": symbol, "qty": qty}})
        try:
            response = self.session.delete(url, params=params)
            response.raise_for_status()
            order_response = OrderResponse.model_validate(response.json())
            log.info("alpaca.close_position.success", extra={"extra": {"order_response": order_response.model_dump()}})
            return order_response
        except requests.RequestException:
            log.error("alpaca.close_position.fail", extra={"extra": {"symbol": symbol}}, exc_info=True)
            raise

    def get_orders(self, status: str = "open"):
        """
        Fetches orders from Alpaca, defaulting to open orders.
        """
        url = f"{self.api_base}/v2/orders"
        params = {"status": status}
        log.info("alpaca.get_orders.start", extra={"extra": {"status": status}})
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            log.info("alpaca.get_orders.success", extra={"extra": {"count": len(data)}})
            return [OrderResponse(**order) for order in data]
        except requests.RequestException:
            log.error("alpaca.get_orders.fail", exc_info=True)
            return []

def get_alpaca_client(api_base: str, max_retries: int = 3, backoff_factor: float = 0.3) -> AlpacaClient:
    """
    Configures and returns an AlpacaClient with a session that has retry logic.
    """
    from smartcfd.alpaca import build_headers_from_env

    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(build_headers_from_env())
    
    return AlpacaClient(api_base, session)
