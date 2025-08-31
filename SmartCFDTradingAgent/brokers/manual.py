from __future__ import annotations

import json, datetime as dt
from pathlib import Path
import logging

from .base import Broker
from SmartCFDTradingAgent.utils.telegram import send as tg_send


class ManualBroker(Broker):
    """Broker that does not execute trades but logs tickets for manual execution."""

    def __init__(self, ticket_dir: str | Path | None = None):
        base = Path(ticket_dir or Path.cwd() / "logs" / "trade_tickets")
        base.mkdir(parents=True, exist_ok=True)
        self.ticket_dir = base
        self.log = logging.getLogger("manual-broker")

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
    ) -> dict:
        ticket = {
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "trail_atr": trail_atr,
            "tif": tif,
            "dry_run": True,
        }
        msg = (
            f"{side.upper()} {symbol} qty={qty} entry={entry} sl={sl} tp={tp}"
        )
        try:
            tg_send(msg)
        except Exception as e:  # pragma: no cover - logging only
            self.log.error("Telegram send failed: %s", e)

        fname = f"{dt.datetime.now(dt.timezone.utc).isoformat().replace(':','-')}_{symbol}_{side}.json"
        path = self.ticket_dir / fname
        try:
            path.write_text(json.dumps(ticket), encoding="utf-8")
        except Exception as e:  # pragma: no cover
            self.log.error("Failed to write ticket: %s", e)
        return ticket
