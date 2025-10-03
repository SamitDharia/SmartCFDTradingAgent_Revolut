from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Iterable

from SmartCFDTradingAgent.pipeline import read_last_decisions
from SmartCFDTradingAgent.utils.trade_logger import aggregate_trade_stats


STORE = Path(__file__).resolve().parent / "storage"
REPORTS_DIR = Path("reports")


FRIENDLY_SIDE = {
    "Buy": "Buy (go long)",
    "Sell": "Sell (go short)",
    "Hold": "Hold / No action",
}


class Digest:
    """Utility to produce plain-language summaries for non-traders."""

    def __init__(self, timezone: str = "Europe/Dublin") -> None:
        self.timezone = timezone

    def latest_decisions(self, count: int = 5) -> list[dict[str, str]]:
        try:
            return read_last_decisions(count)
        except Exception:
            return []

    def trade_stats(self) -> dict[str, int]:
        try:
            return aggregate_trade_stats()
        except Exception:
            return {"wins": 0, "losses": 0, "open": 0}

    def describe_decision(self, row: dict[str, str]) -> str:
        side = FRIENDLY_SIDE.get(row.get("side", ""), row.get("side", ""))
        price = row.get("price", "?")
        sl = row.get("sl") or "not set"
        tp = row.get("tp") or "not set"
        interval = row.get("interval", "1d")
        adx = row.get("adx", "?")
        return (
            f"• {row.get('ticker', 'ticker?')} → {side} around {price}. "
            f"Stop {sl}, target {tp}. Timeframe: {interval}, ADX filter {adx}."
        )

    def generate_text(self, decisions: int = 5) -> str:
        now = dt.datetime.now().strftime("%A %d %B %Y %H:%M")
        stats = self.trade_stats()
        rows = self.latest_decisions(decisions)

        parts: list[str] = []
        parts.append(f"Daily Trading Digest — {now}")
        parts.append("")
        parts.append("How are we doing?")
        parts.append(
            f"- Wins: {stats.get('wins', 0)} | Losses: {stats.get('losses', 0)} | Open positions: {stats.get('open', 0)}"
        )
        parts.append(
            "- What this means: the agent keeps risk small by using ATR (Average True Range), "
            "which measures a market's typical wiggle. Bigger ATR → smaller position size."
        )
        parts.append("")

        if rows:
            parts.append("Fresh trade ideas to review:")
            for row in rows:
                parts.append(self.describe_decision(row))
        else:
            parts.append("No new trade ideas logged yet today. The system will message you when something pops up.")
        parts.append("")

        parts.append("Next steps for you:")
        parts.append("1. Open your broker dashboard. Confirm the entry price and set the stop-loss and target shown above.")
        parts.append("2. If this is paper trading only, simply observe how the positions behave and take notes.")
        parts.append(
            "3. Got an alert that says 'Data download failed'? That just means the data feed was busy. The next "
            "scheduled run will try again automatically."
        )
        parts.append("")

        parts.append("Glossary (plain language):")
        parts.append("- ATR: tells us how much the price tends to move. Bigger ATR → we buy fewer shares.")
        parts.append("- Stop-loss: automatic exit if price goes the wrong way, keeps losses capped.")
        parts.append("- Take-profit: automatic exit when the price reaches the goal.")
        parts.append("- ADX: measures trend strength. Higher number usually means a stronger trend.")
        parts.append("")

        parts.append("Questions or need help? Reply to this Telegram message and we’ll walk you through the setup.")

        return "\n".join(parts)

    def save_digest(self, content: str, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def dump_json(self, rows: Iterable[dict[str, str]], path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": dt.datetime.utcnow().isoformat(),
            "decisions": list(rows),
            "stats": self.trade_stats(),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


__all__ = ["Digest"]
