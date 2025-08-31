from __future__ import annotations

from .manual import ManualBroker


def get_broker(name: str):
    name = (name or "").lower()
    if name == "manual":
        return ManualBroker()
    raise ValueError(f"Unknown broker: {name}")
