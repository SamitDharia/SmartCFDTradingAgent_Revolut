from __future__ import annotations

import logging
import os
from typing import Any, Dict

TRUTHY = {"1", "true", "yes", "on"}


def _env_first(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def _env_flag(*names: str) -> bool | None:
    for name in names:
        if name in os.environ:
            return os.getenv(name, "").strip().lower() in TRUTHY
    return None

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
        resolved_key = key_id or _env_first("APCA_API_KEY_ID", "ALPACA_API_KEY", "ALPACA_API_KEY_ID")
        resolved_secret = secret_key or _env_first("APCA_API_SECRET_KEY", "ALPACA_API_SECRET", "ALPACA_API_SECRET_KEY")
        resolved_base = base_url or _env_first("APCA_API_BASE_URL", "ALPACA_API_BASE_URL")
        if resolved_base is None:
            paper_flag = _env_flag("APCA_PAPER", "ALPACA_PAPER")
            if paper_flag is False:
                resolved_base = "https://api.alpaca.markets"
            else:
                resolved_base = "https://paper-api.alpaca.markets"
        if not resolved_key or not resolved_secret:
            self.log.warning("Alpaca credentials missing; REST client may be unauthorized.")
        self.api = tradeapi.REST(
            resolved_key,
            resolved_secret,
            resolved_base,
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
        except Exception as e:  # pragma: no cover - runtime logging
            self.log.error("Invalid account equity: %s", e)
            return None

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

        # Alpaca uses 'BTC/USD' for crypto symbols
        alpaca_symbol = symbol.replace('-', '/') if '-' in (symbol or '') else symbol

        params: Dict[str, Any] = {
            "symbol": alpaca_symbol,
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
