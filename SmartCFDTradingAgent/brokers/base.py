from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class Broker(ABC):
    @abstractmethod
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
        """Submit an order and return a summary dictionary."""
        raise NotImplementedError
