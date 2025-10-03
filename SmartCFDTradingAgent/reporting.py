from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Iterable

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from SmartCFDTradingAgent.pipeline import read_last_decisions
from SmartCFDTradingAgent.utils.trade_logger import aggregate_trade_stats


STORE = Path(__file__).resolve().parent / "storage"
REPORTS_DIR = Path("reports")


FRIENDLY_SIDE = {
    "Buy": "Buy",
    "Sell": "Sell",
    "Hold": "Hold",
}


class Digest:
    """Produce plain-language summaries for non-traders."""

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

    def yesterday_snapshot(self) -> dict[str, float] | None:
        trade_log = STORE / "trade_log.csv"
        if not trade_log.exists():
            return None
        try:
            df = pd.read_csv(trade_log, parse_dates=["time"])
        except Exception:
            return None
        if df.empty or "time" not in df.columns:
            return None

        today = dt.datetime.now().date()
        yday = today - dt.timedelta(days=1)
        df = df.dropna(subset=["time"])
        df["date"] = pd.to_datetime(df["time"]).dt.date
        rows = df[df["date"] == yday]
        if rows.empty:
            return None

        def _pnl(row: pd.Series) -> float:
            entry = row.get("entry")
            exit_ = row.get("exit")
            if pd.isna(entry) or pd.isna(exit_):
                return 0.0
            side = str(row.get("side", "")).lower()
            if side == "sell":
                return float(entry) - float(exit_)
            return float(exit_) - float(entry)

        closed = rows.dropna(subset=["exit"])
        wins = 0
        losses = 0
        pnl = 0.0
        for _, row in closed.iterrows():
            entry = row.get("entry")
            exit_ = row.get("exit")
            if pd.isna(entry) or pd.isna(exit_):
                continue
            side = str(row.get("side", "")).lower()
            if side == "sell":
                if float(exit_) < float(entry):
                    wins += 1
                elif float(exit_) > float(entry):
                    losses += 1
            else:
                if float(exit_) > float(entry):
                    wins += 1
                elif float(exit_) < float(entry):
                    losses += 1
            pnl += _pnl(row)
        return {
            "total": int(len(closed)),
            "wins": int(wins),
            "losses": int(losses),
            "open": int(len(rows) - len(closed)),
            "pnl": float(round(pnl, 2)),
        }

    def save_snapshot_chart(self, snapshot: dict[str, float] | None, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not snapshot:
            if path.exists():
                try:
                    path.unlink()
                except Exception:
                    pass
            return

        labels = ["Wins", "Losses", "Open"]
        values = [snapshot.get("wins", 0), snapshot.get("losses", 0), snapshot.get("open", 0)]
        fig, ax = plt.subplots(figsize=(4, 3))
        colors = ["#2ca02c", "#d62728", "#1f77b4"]
        ax.bar(labels, values, color=colors)
        ax.set_ylabel("Count of trades")
        ax.set_title("Yesterday's results")
        ax.grid(axis="y", linestyle="--", alpha=0.2)
        ax.text(0.5, -0.25, f"Net P/L: {snapshot.get('pnl', 0.0):+.2f}", ha="center", transform=ax.transAxes)
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)

    def describe_decision(self, row: dict[str, str]) -> str:
        side = FRIENDLY_SIDE.get(row.get("side", ""), row.get("side", ""))
        price = row.get("price", "?")
        sl = row.get("sl") or "not set"
        tp = row.get("tp") or "not set"
        interval = row.get("interval", "1d")
        adx = row.get("adx", "?")
        return (
            f"- {row.get('ticker', 'ticker?')}: {side} near {price} | "
            f"Stop {sl} | Target {tp} | Timeframe {interval} | Trend filter ADX {adx}"
        )

    def generate_text(self, decisions: int = 5) -> str:
        now = dt.datetime.now().strftime("%A %d %B %Y %H:%M")
        stats = self.trade_stats()
        rows = self.latest_decisions(decisions)
        snapshot = self.yesterday_snapshot()
        chart_path = REPORTS_DIR / "daily_digest.png"
        self.save_snapshot_chart(snapshot, chart_path)

        parts: list[str] = []
        parts.append(f"Daily Trading Digest — {now}")
        parts.append("")

        parts.append("How are we doing?")
        parts.append(
            f"- Total closed trades so far: Wins {stats.get('wins', 0)}, Losses {stats.get('losses', 0)}, Open {stats.get('open', 0)}"
        )
        parts.append(
            "- What this means: the agent keeps risk small by using ATR (Average True Range), "
            "which measures a market's typical wiggle. Bigger ATR means the system automatically places smaller trades."
        )
        if snapshot:
            parts.append(
                f"- Yesterday: {snapshot['total']} closed (Wins {snapshot['wins']} | Losses {snapshot['losses']} | Open {snapshot['open']}) — Net P/L {snapshot['pnl']:+.2f}"
            )
            win_bar = '█' * max(snapshot['wins'], 1)
            loss_bar = '█' * max(snapshot['losses'], 1)
            parts.append(f"  Wins [{win_bar}]  Losses [{loss_bar}]")
            parts.append(f"  Chart saved to {chart_path}")
        else:
            parts.append("- Yesterday: no closed trades recorded.")
        parts.append("")

        parts.append("Fresh trade ideas to review:")
        if rows:
            for row in rows:
                parts.append(self.describe_decision(row))
        else:
            parts.append("- No new trade ideas yet. The agent will alert you as soon as one appears.")
        parts.append("")

        parts.append("Next steps for you:")
        parts.append("1. Open your broker app. Place any trade you like from the list above, including stop-loss and target.")
        parts.append("2. Prefer to watch? Just log in later and check the digest for updates.")
        parts.append("3. Any alerts about data issues? They simply mean the data feed was busy. The next run re-tries automatically.")
        parts.append("")

        parts.append("Glossary (plain language):")
        parts.append("- ATR: measures how much the price usually moves; bigger ATR = smaller position size.")
        parts.append("- Stop-loss: automatic exit if price moves against us too far.")
        parts.append("- Take-profit: automatic exit when price hits our goal.")
        parts.append("- ADX: trend strength indicator; higher values usually mean a stronger trend.")
        parts.append("")

        parts.append("Questions? Reply to this Telegram message and we’ll help you out.")

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
