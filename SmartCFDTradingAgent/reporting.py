from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Iterable, Tuple, Optional

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

    # ------------------------------------------------------------------ helpers
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
            entry = float(entry)
            exit_ = float(exit_)
            side = str(row.get("side", "")).lower()
            return entry - exit_ if side == "sell" else exit_ - entry

        closed = rows.dropna(subset=["exit"])
        wins = 0
        losses = 0
        pnl = 0.0
        for _, row in closed.iterrows():
            entry = row.get("entry")
            exit_ = row.get("exit")
            if pd.isna(entry) or pd.isna(exit_):
                continue
            entry = float(entry)
            exit_ = float(exit_)
            side = str(row.get("side", "")).lower()
            if side == "sell":
                wins += int(exit_ < entry)
                losses += int(exit_ > entry)
            else:
                wins += int(exit_ > entry)
                losses += int(exit_ < entry)
            pnl += _pnl(row)
        return {
            "total": int(len(closed)),
            "wins": int(wins),
            "losses": int(losses),
            "open": int(len(rows) - len(closed)),
            "pnl": float(round(pnl, 2)),
        }

    def save_snapshot_chart(self, snapshot: dict[str, float] | None) -> Optional[Path]:
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
        colors = ["#22c55e", "#ef4444", "#3b82f6"]
        fig, ax = plt.subplots(figsize=(4.2, 3.2))
        ax.bar(labels, values, color=colors, width=0.55)
        ax.set_ylabel("Trades", color="#0f172a")
        ax.set_title("Yesterday's results", color="#0f172a", pad=10)
        ax.grid(axis="y", linestyle="--", alpha=0.25)
        ax.set_facecolor("#f8fafc")
        fig.patch.set_facecolor("#f8fafc")
        ax.text(0.5, -0.25, f"Net P/L: {snapshot.get('pnl', 0.0):+.2f}", ha="center", transform=ax.transAxes, color="#334155")
        fig.tight_layout()
        fig.savefig(CHART_PATH, dpi=150)
        plt.close(fig)
        return CHART_PATH

    # ----------------------------------------------------------- content helpers
    def describe_decision(self, row: dict[str, str]) -> str:
        side = FRIENDLY_SIDE.get(row.get("side", ""), row.get("side", ""))
        price = row.get("price", "?")
        sl = row.get("sl") or "not set"
        tp = row.get("tp") or "not set"
        interval = row.get("interval", "1d")
        adx = row.get("adx", "?")
        return (
            f"- {row.get('ticker', 'ticker?')}: {side} near {price} | stop {sl} | target {tp} | timeframe {interval} | ADX {adx}"
        )

    # ------------------------------------------------------------ email content
    def build_email_content(self, decisions: int = 5) -> Tuple[str, str, Optional[Path]]:
        now = dt.datetime.now().strftime("%A %d %B %Y %H:%M")
        stats = self.trade_stats()
        rows = self.latest_decisions(decisions)
        snapshot = self.yesterday_snapshot()
        chart_path = self.save_snapshot_chart(snapshot)

        # Plain text (fallback)
        plain_lines: list[str] = []
        plain_lines.append(f"Daily Trading Digest — {now}")
        plain_lines.append("")
        plain_lines.append("How did we do yesterday?")
        plain_lines.append(
            f"- Overall totals: Wins {stats.get('wins', 0)}, Losses {stats.get('losses', 0)}, Open {stats.get('open', 0)}"
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
        plain_lines.append("2. Prefer to watch? Visit the dashboard: http://localhost:8501")
        plain_lines.append("3. Keep notes on what interests you for future review.")
        plain_lines.append("")

        plain_lines.append("Glossary:")
        plain_lines.append("- ATR: measures how much the price usually moves; bigger ATR = smaller position size.")
        plain_lines.append("- Stop-loss: automatic exit if price moves against us too far.")
        plain_lines.append("- Take-profit: automatic exit when price hits the goal.")
        plain_lines.append("- ADX: trend strength indicator; higher values usually mean a stronger trend.")
        plain_lines.append("")
        plain_lines.append("Questions? Reply to this email and we'll help you out.")

        plain_text = "
".join(plain_lines)

        # HTML styling
        css = """
        <style>
        body {{background:#f4f6fb;font-family:'Segoe UI',Arial,sans-serif;color:#0f172a;margin:0;padding:24px;}}
        .wrapper {{max-width:720px;margin:auto;background:#ffffff;border-radius:16px;padding:32px;
                   box-shadow:0 22px 40px rgba(15,23,42,0.12);}}
        h2 {{margin-top:0;font-weight:700;color:#0f172a;}}
        .section {{margin-bottom:24px;}}
        .card {{background:#f8fafc;border-radius:12px;padding:16px;margin-top:12px;}}
        .metric {{display:flex;gap:12px;align-items:center;margin:6px 0;}}
        .metric span.icon {{font-size:18px;}}
        .ideas li {{margin-bottom:8px;}}
        .footer {{font-size:12px;color:#64748b;margin-top:32px;}}
        </style>
        """

        chart_html = (
            f"<div class='card'><strong>Yesterday chart</strong><br /><img src='cid:daily_chart' alt='Yesterday results chart' style='max-width:360px;border-radius:8px;margin-top:8px;'/></div>"
            if chart_path
            else "<div class='card'><strong>Yesterday chart</strong><br /><span style='color:#94a3b8;'>No closed trades yesterday.</span></div>"
        )

        ideas_html = "".join(
            f"<li>🥇 <strong>{row.get('ticker')}</strong> — {FRIENDLY_SIDE.get(row.get('side',''), row.get('side',''))} near {row.get('price','?')}"             f" <span style='color:#64748b;'>SL {row.get('sl','-')} · TP {row.get('tp','-')} · TF {row.get('interval','1d')} · ADX {row.get('adx','?')}</span></li>"
            for row in rows
        ) if rows else "<li>No new trade ideas yet. We'll alert you when one appears.</li>"

        snapshot_html = (
            f"<div class='card'><div class='metric'><span class='icon'>📊</span><div><strong>Yesterday</strong><br />"
            f"{snapshot['total']} closed · Wins {snapshot['wins']} · Losses {snapshot['losses']} · Open {snapshot['open']} · Net P/L <strong>{snapshot['pnl']:+.2f}</strong></div></div></div>"
            if snapshot else "<div class='card'><div class='metric'><span class='icon'>📊</span><div><strong>Yesterday</strong><br />No closed trades recorded.</div></div></div>"
        )

        html = f"""
        <html>
          <head><meta charset='utf-8'/>{css}</head>
          <body>
            <div class='wrapper'>
              <h2>📈 Daily Trading Digest — {now}</h2>
              <div class='section'>
                <div class='metric'><span class='icon'>✅</span><div><strong>Overall totals</strong><br/>Wins {stats.get('wins',0)}, Losses {stats.get('losses',0)}, Open {stats.get('open',0)}</div></div>
                <div class='metric'><span class='icon'>🛡️</span><div><strong>What this means</strong><br/>ATR keeps risk steady — bigger ATR automatically means smaller trade size.</div></div>
                {snapshot_html}
                {chart_html}
              </div>
              <div class='section'>
                <p><strong>💡 Fresh trade ideas</strong></p>
                <ul class='ideas'>
                  {ideas_html}
                </ul>
              </div>
              <div class='section'>
                <p><strong>🧭 Next steps</strong></p>
                <ol>
                  <li>Open your broker and place any ideas you like (with stop & target).</li>
                  <li>Prefer to watch? Visit the dashboard: <a href='http://localhost:8501' style='color:#2563eb;'>http://localhost:8501</a></li>
                  <li>Keep notes on what interests you for future review.</li>
                </ol>
              </div>
              <div class='section'>
                <p><strong>📘 Glossary</strong></p>
                <ul>
                  <li><strong>ATR</strong>: measures how much the price usually moves; bigger ATR = smaller position size.</li>
                  <li><strong>Stop-loss</strong>: automatic exit if price moves against us.</li>
                  <li><strong>Take-profit</strong>: automatic exit when price hits the goal.</li>
                  <li><strong>ADX</strong>: trend strength indicator; higher values usually mean a stronger trend.</li>
                </ul>
              </div>
              <p class='footer'>Questions? Reply to this email and we’ll help you out.</p>
            </div>
          </body>
        </html>
        """

        return plain_text, html, chart_path

    # ---------------------------------------------------------- telegram digest
    def build_telegram_message(self, decisions: int = 3) -> str:
        now = dt.datetime.now().strftime("%d %b %H:%M")
        stats = self.trade_stats()
        rows = self.latest_decisions(decisions)
        snapshot = self.yesterday_snapshot()

        lines = [f"Crypto Digest {now}"]
        lines.append(f"Wins {stats.get('wins',0)} / Losses {stats.get('losses',0)} / Open {stats.get('open',0)}")
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
        return "
".join(lines)

    # ------------------------------------------------------------- persistence
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
