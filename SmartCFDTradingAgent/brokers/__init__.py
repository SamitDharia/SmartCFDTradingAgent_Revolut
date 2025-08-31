from __future__ import annotations

from .manual import ManualBroker
from .alpaca import AlpacaBroker


def get_broker(name: str):
    name = (name or "").lower()
    if name == "manual":
        return ManualBroker()
    if name == "alpaca":
        return AlpacaBroker()
    raise ValueError(f"Unknown broker: {name}")
