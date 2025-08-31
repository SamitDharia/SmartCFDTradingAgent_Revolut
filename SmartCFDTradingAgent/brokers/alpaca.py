from __future__ import annotations

import logging
import os
from typing import Any, Dict

try:  # pragma: no cover - handled in tests via monkeypatch
    import alpaca_trade_api as tradeapi
except Exception:  # pragma: no cover
    tradeapi = None  # type: ignore

from .base import Broker


class AlpacaBroker(Broker):
    """Broker implementation using Alpaca's paper trading API."""

    def __init__(
        self,
        key_id: str | None = None,
        secret_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        if tradeapi is None:  # pragma: no cover - dependency missing
            raise RuntimeError("alpaca-trade-api package required")
        self.log = logging.getLogger("alpaca-broker")
        self.api = tradeapi.REST(
            key_id or os.getenv("APCA_API_KEY_ID"),
            secret_key or os.getenv("APCA_API_SECRET_KEY"),
            base_url or os.getenv("APCA_API_BASE_URL", "https://paper-api.alpaca.markets"),
            api_version="v2",
        )

    # --- helper methods ---
    def get_equity(self) -> float | None:
        """Return account equity from Alpaca."""
        try:
            acct = self.api.get_account()
        except Exception as e:  # pragma: no cover - runtime logging
            self.log.error("Account retrieval failed: %s", e)
            return None

        try:
            return float(getattr(acct, "equity", 0.0))
        except Exception:
            return 0.0

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
        order: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "trail_atr": trail_atr,
            "tif": tif,
            "dry_run": dry_run,
        }
        if dry_run:
            return order

        params: Dict[str, Any] = {
            "symbol": symbol,
            "qty": qty,
            "side": side.lower(),
            "type": "market",
            "time_in_force": tif,
        }
        if sl is not None or tp is not None:
            params["order_class"] = "bracket"
            if tp is not None:
                params["take_profit"] = {"limit_price": tp}
            if sl is not None:
                params["stop_loss"] = {"stop_price": sl}
        try:
            result = self.api.submit_order(**params)
            order["id"] = getattr(result, "id", None)
            order["status"] = getattr(result, "status", "")
        except Exception as e:  # pragma: no cover - runtime logging
            self.log.error("Order submission failed: %s", e)
            raise
        return order
