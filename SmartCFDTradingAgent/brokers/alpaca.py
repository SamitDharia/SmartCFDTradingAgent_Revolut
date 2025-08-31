from __future__ import annotations

import os, logging, importlib
from typing import Any, Dict

from .base import Broker


class AlpacaBroker(Broker):
    def __init__(self) -> None:
        self.log = logging.getLogger("alpaca-broker")
        self.api_key = os.getenv("ALPACA_API_KEY", "").strip()
        self.api_secret = os.getenv("ALPACA_API_SECRET", "").strip()
        paper = os.getenv("ALPACA_PAPER", "true").lower() == "true"
        self.base_url = (
            "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
        )
        self.allow_fractional = os.getenv("ALLOW_FRACTIONAL", "false").lower() == "true"

        self.client = None
        try:
            tradeapi = importlib.import_module("alpaca_trade_api")
            if self.api_key and self.api_secret:
                self.client = tradeapi.REST(
                    self.api_key, self.api_secret, base_url=self.base_url
                )
        except Exception:
            self.client = None

    def submit_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        entry: float | None = None,
        sl: float | None = None,
        tp: float | None = None,
        trail_atr: float | None = None,
        tif: str = "day",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        qty_val: Any = float(qty) if self.allow_fractional else int(qty)
        order_args: Dict[str, Any] = {
            "symbol": symbol,
            "side": side.lower(),
            "type": "market" if entry is None else "limit",
            "qty": qty_val,
            "time_in_force": tif,
        }
        if entry is not None:
            order_args["limit_price"] = entry
        if sl or tp:
            order_args["order_class"] = "bracket"
            if tp:
                order_args["take_profit"] = {"limit_price": tp}
            if sl:
                order_args["stop_loss"] = {"stop_price": sl}

        if dry_run or self.client is None:
            return {"submitted": False, **order_args}

        resp = self.client.submit_order(**order_args)
        order_id = getattr(resp, "id", None)
        return {"submitted": True, "id": order_id, **order_args}
