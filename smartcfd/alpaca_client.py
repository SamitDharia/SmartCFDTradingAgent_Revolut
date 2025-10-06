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

    def post_order(self, order_data: OrderRequest) -> OrderResponse:
        """
        Posts an order to the Alpaca API.
        
        Raises:
            requests.HTTPError: If the API returns a non-2xx status code.
        """
        url = f"{self.api_base}/v2/orders"
        try:
            # Use by_alias to correctly serialize 'type' to 'type'
            response = self.session.post(url, json=order_data.model_dump(by_alias=True))
            response.raise_for_status()
            return OrderResponse.model_validate(response.json())
        except requests.RequestException as e:
            log.error("alpaca.post_order.fail", extra={"extra": {"error": repr(e), "order": order_data.model_dump()}})
            raise
        except Exception as e:
            log.error("alpaca.post_order.parse_fail", extra={"extra": {"error": repr(e)}})
            raise

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
