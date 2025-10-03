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
CHART_PATH = REPORTS_DIR / "daily_digest.png"


FRIENDLY_SIDE = {
    "Buy": "Buy",
    "Sell": "Sell",
    "Hold": "Hold",
}


class Digest:
    """Produce friendly digest content for email/Telegram."""

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
            entry = float(entry)
            exit_ = float(exit_)
            if side == "sell":
                return entry - exit_
            return exit_ - entry

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
            entry = float(entry)
            exit_ = float(exit_)
            if side == "sell":
                if exit_ < entry:
                    wins += 1
                elif exit_ > entry:
                    losses += 1
            else:
                if exit_ > entry:
                    wins += 1
                elif exit_ < entry:
                    losses += 1
            pnl += _pnl(row)
        return {
            "total": int(len(closed)),
            "wins": int(wins),
            "losses": int(losses),
            "open": int(len(rows) - len(closed)),
            "pnl": float(round(pnl, 2)),
        }

    def save_snapshot_chart(self, snapshot: dict[str, float] | None) -> Path | None:
        CHART_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not snapshot:
            if CHART_PATH.exists():
                try:
                    CHART_PATH.unlink()
                except Exception:
                    pass
            return None

        labels = ["Wins", "Losses", "Open"]
        values = [snapshot.get("wins", 0), snapshot.get("losses", 0), snapshot.get("open", 0)]
        colors = ["#2ca02c", "#d62728", "#1f77b4"]
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.bar(labels, values, color=colors)
        ax.set_ylabel("Trades")
        ax.set_title("Yesterday's results")
        ax.grid(axis="y", linestyle="--", alpha=0.2)
        ax.text(0.5, -0.25, f"Net P/L: {snapshot.get('pnl', 0.0):+.2f}", ha="center", transform=ax.transAxes)
        fig.tight_layout()
        fig.savefig(CHART_PATH, dpi=150)
        plt.close(fig)
        return CHART_PATH

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

    def build_email_content(self, decisions: int = 5) -> tuple[str, str, Path | None]:
        now = dt.datetime.now().strftime("%A %d %B %Y %H:%M")
        stats = self.trade_stats()
        rows = self.latest_decisions(decisions)
        snapshot = self.yesterday_snapshot()
        chart_path = self.save_snapshot_chart(snapshot)

        plain_lines: list[str] = []
        plain_lines.append(f"Daily Trading Digest — {now}")
        plain_lines.append("")
        plain_lines.append("How did we do yesterday?")
        plain_lines.append(
            f"- Overall: Wins {stats.get('wins', 0)}, Losses {stats.get('losses', 0)}, Open {stats.get('open', 0)}"
        )
        if snapshot:
            plain_lines.append(
                f"- Yesterday: {snapshot['total']} closed (Wins {snapshot['wins']} | Losses {snapshot['losses']} | Open {snapshot['open']}) — Net P/L {snapshot['pnl']:+.2f}"
            )
        else:
            plain_lines.append("- Yesterday: no closed trades recorded.")
        plain_lines.append(
            "- What this means: ATR (Average True Range) keeps risk steady — bigger ATR automatically means smaller trade size."
        )
        plain_lines.append("")

        plain_lines.append("Fresh trade ideas:")
        if rows:
            for row in rows:
                plain_lines.append(self.describe_decision(row))
        else:
            plain_lines.append("- No new trade ideas yet. We'll alert you when one appears.")
        plain_lines.append("")

        plain_lines.append("Next steps:")
        plain_lines.append("1. Open your broker and place any ideas you like (with stop & target).")
        plain_lines.append("2. Prefer to watch? Check the dashboard: http://localhost:8501")
        plain_lines.append("3. Keep notes on what interests you for future review.")
        plain_lines.append("")

        plain_lines.append("Glossary:")
        plain_lines.append("- ATR: measures typical price movement; bigger ATR → smaller position size.")
        plain_lines.append("- Stop-loss: automatic exit if price goes too far against us.")
        plain_lines.append("- Take-profit: automatic exit when price reaches the goal.")
        plain_lines.append("- ADX: trend strength indicator; higher values usually mean a stronger trend.")

        plain_text = "\n".join(plain_lines)

        html_rows = "".join(
            f"<li>🥇 <strong>{row.get('ticker')}</strong>: {FRIENDLY_SIDE.get(row.get('side',''), row.get('side',''))} near {row.get('price','?')} &nbsp;"
            f"<span style='color:#999'>SL {row.get('sl','-')} | TP {row.get('tp','-')} | TF {row.get('interval','1d')} | ADX {row.get('adx','?')}</span></li>"
            for row in rows
        ) if rows else "<li>No new trade ideas yet. We'll alert you when one appears.</li>"

        html_snapshot = (
            f"<p>📊 <strong>Yesterday:</strong> {snapshot['total']} closed (Wins {snapshot['wins']} | Losses {snapshot['losses']} | Open {snapshot['open']}) — Net P/L <strong>{snapshot['pnl']:+.2f}</strong></p>"
            if snapshot else "<p>📊 <strong>Yesterday:</strong> No closed trades recorded.</p>"
        )

        chart_img = (
            f"<p><img src='cid:daily_chart' alt='Yesterday results chart' style='max-width:360px;border:1px solid #eee;border-radius:6px;'/></p>"
            if chart_path and chart_path.exists() else ""
        )

        html = f"""
<html>
  <body style="font-family:'Segoe UI',Arial,sans-serif;background:#f9fbfc;color:#1f2a33;padding:16px;">
    <div style="max-width:720px;margin:auto;background:#ffffff;border-radius:12px;box-shadow:0 4px 16px rgba(15,23,42,0.08);padding:24px;">
      <h2 style="margin-top:0;color:#0f172a;">📈 Daily Trading Digest — {now}</h2>
      <section style="margin-bottom:18px;">
        <p>📌 <strong>How did we do yesterday?</strong></p>
        <p>✅ <strong>Overall</strong>: Wins {stats.get('wins',0)}, Losses {stats.get('losses',0)}, Open {stats.get('open',0)}</p>
        {html_snapshot}
        <p>🛡️ <strong>What this means:</strong> ATR (Average True Range) keeps risk steady — bigger ATR automatically means smaller trade size.</p>
        {chart_img}
      </section>
      <section style="margin-bottom:18px;">
        <p>💡 <strong>Fresh trade ideas:</strong></p>
        <ul style="padding-left:20px;margin-top:8px;margin-bottom:8px;">
          {html_rows}
        </ul>
      </section>
      <section style="margin-bottom:18px;">
        <p>🧭 <strong>Next steps:</strong></p>
        <ol style="padding-left:20px;margin-top:8px;margin-bottom:8px;">
          <li>Open your broker and place any ideas you like (with stop & target).</li>
          <li>Prefer to watch? Explore the dashboard ↗ <a href="http://localhost:8501" style="color:#2563eb;">http://localhost:8501</a></li>
          <li>Keep notes on anything interesting for future review.</li>
        </ol>
      </section>
      <section style="margin-bottom:18px;">
        <p>📘 <strong>Glossary:</strong></p>
        <ul style="padding-left:20px;margin-top:8px;margin-bottom:8px;">
          <li><strong>ATR</strong>: measures typical price movement; bigger ATR → smaller position size.</li>
          <li><strong>Stop-loss</strong>: automatic exit if price moves against us.</li>
          <li><strong>Take-profit</strong>: automatic exit when price hits the goal.</li>
          <li><strong>ADX</strong>: trend strength indicator; higher values usually mean stronger trend.</li>
        </ul>
      </section>
      <p style="font-size:12px;color:#6b7280;margin-top:24px;">Questions? Reply to this email and we’ll help you out.</p>
    </div>
  </body>
</html>
"""

        return plain_text, html, chart_path if chart_path and chart_path.exists() else None

    def build_telegram_message(self, decisions: int = 3) -> str:
        now = dt.datetime.now().strftime("%d %b %H:%M")
        stats = self.trade_stats()
        rows = self.latest_decisions(decisions)
        snapshot = self.yesterday_snapshot()

        lines = [f"Crypto Digest {now}"]
        lines.append(f"Wins {stats.get('wins',0)}, Losses {stats.get('losses',0)}, Open {stats.get('open',0)}")
        if snapshot:
            lines.append(f"Yesterday: {snapshot['total']} closed | PnL {snapshot['pnl']:+.2f}")
        else:
            lines.append("Yesterday: no closed trades")
        lines.append("Ideas:")
        if rows:
            for row in rows:
                lines.append(
                    f"• {row.get('ticker')} {row.get('side','Hold')} @ {row.get('price')} (SL {row.get('sl','-')} / TP {row.get('tp','-')})"
                )
        else:
            lines.append("• No new trades yet")
        return "\n".join(lines)

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


__all__ = ["Digest", "CHART_PATH"]
