from pydantic import BaseModel, Field
from typing import Any, Optional, Literal

class Order(BaseModel):
    """A standardized model for an order."""
    id: str
    symbol: str
    qty: float
    side: str
    status: str
    filled_qty: Optional[float] = None
    filled_avg_price: Optional[float] = None
    created_at: Any

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

class TradeGroup(BaseModel):
    """
    Represents the state of a client-side OCO trade group.
    """
    gid: str
    symbol: str
    side: str
    status: str
    entry_order_id: Optional[str] = None
    entry_filled_qty: Optional[float] = None
    tp_order_id: Optional[str] = None
    sl_order_id: Optional[str] = None
    open_qty: Optional[float] = None
    created_at: str
    updated_at: str
    note: Optional[str] = None
