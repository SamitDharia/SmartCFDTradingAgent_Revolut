from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

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

    def simulate_recommended_trades(self, target_date: Optional[dt.date] | None = None) -> dict[str, object] | None:
        decision_log = STORE / "decision_log.csv"
        if not decision_log.exists():
            return None
        try:
            df = pd.read_csv(decision_log)
        except Exception:
            return None
        if df.empty or "ts" not in df.columns:
            return None

        df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
        df = df.dropna(subset=["ts", "price"])
        if df.empty:
            return None

        if target_date is None:
            target_date = dt.datetime.now().date() - dt.timedelta(days=1)

        df["date"] = df["ts"].dt.date
        subset = df[df["date"] == target_date]
        if subset.empty:
            return {
                "date": target_date,
                "items": [],
                "count": 0,
                "count_with_levels": 0,
                "total_tp": 0.0,
                "total_sl": 0.0,
                "average_r": None,
            }

        def _to_float(value: object) -> float | None:
            if pd.isna(value):
                return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        items: list[dict[str, object]] = []
        total_tp = 0.0
        total_sl = 0.0
        count_with_levels = 0
        r_values: list[float] = []

        for row in subset.itertuples():
            entry = _to_float(getattr(row, "price", None))
            tp = _to_float(getattr(row, "tp", None))
            sl = _to_float(getattr(row, "sl", None))
            side = str(getattr(row, "side", "")).strip().lower()

            pnl_tp = None
            pnl_sl = None
            risk = None

            if entry is not None and tp is not None:
                if side == "sell":
                    pnl_tp = entry - tp
                else:
                    pnl_tp = tp - entry
            if entry is not None and sl is not None:
                if side == "sell":
                    pnl_sl = entry - sl
                else:
                    pnl_sl = sl - entry

            if pnl_sl is not None:
                risk = abs(pnl_sl)
            elif entry is not None and sl is not None:
                risk = abs(entry - sl)

            r_multiple = None
            if pnl_tp is not None and risk not in (None, 0):
                r_multiple = pnl_tp / risk if risk else None

            if tp is not None and sl is not None:
                count_with_levels += 1

            if pnl_tp is not None:
                total_tp += pnl_tp
            if pnl_sl is not None:
                total_sl += pnl_sl
            if r_multiple is not None:
                r_values.append(r_multiple)

            items.append(
                {
                    "ticker": getattr(row, "ticker", "?"),
                    "side": getattr(row, "side", "?"),
                    "entry": entry,
                    "tp": tp,
                    "sl": sl,
                    "pnl_tp": pnl_tp,
                    "pnl_sl": pnl_sl,
                    "r_multiple": r_multiple,
                }
            )

        return {
            "date": target_date,
            "items": items,
            "count": int(len(subset)),
            "count_with_levels": int(count_with_levels),
            "total_tp": float(round(total_tp, 2)),
            "total_sl": float(round(total_sl, 2)),
            "average_r": float(round(sum(r_values) / len(r_values), 2)) if r_values else None,
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
        simulation = self.simulate_recommended_trades()
        chart_path = self.save_snapshot_chart(snapshot)

        def _fmt_price(value: object) -> str:
            if value is None:
                return "?"
            try:
                return f"{float(value):.2f}"
            except (TypeError, ValueError):
                return "?"

        def _fmt_signed(value: object) -> str:
            if value is None:
                return "n/a"
            try:
                return f"{float(value):+.2f}"
            except (TypeError, ValueError):
                return "n/a"

        plain_lines: list[str] = []
        plain_lines.append(f"Daily Trading Digest {now}")
        plain_lines.append("")
        plain_lines.append("Yesterday's scorecard:")
        plain_lines.append(
            f"- Lifetime totals: Wins {stats.get('wins', 0)}, Losses {stats.get('losses', 0)}, Open {stats.get('open', 0)}"
        )
        if snapshot:
            plain_lines.append(
                f"- Closed yesterday: {snapshot['total']} (Wins {snapshot['wins']} | Losses {snapshot['losses']} | Still open {snapshot['open']}) | Net P/L {snapshot['pnl']:+.2f}"
            )
        else:
            plain_lines.append("- Closed yesterday: no trades were logged.")
        plain_lines.append("")
        plain_lines.append("Simulated execution (based on yesterday's plans):")
        if simulation and simulation.get("count", 0) > 0:
            plain_lines.append(
                f"- Plans logged: {simulation['count']} (with both exits set: {simulation['count_with_levels']})"
            )
            plain_lines.append(f"- If every target filled: {simulation['total_tp']:+.2f}")
            if simulation.get("count_with_levels", 0) > 0:
                plain_lines.append(f"- If every stop triggered: {simulation['total_sl']:+.2f}")
            if simulation.get("average_r") is not None:
                plain_lines.append(f"- Average reward-to-risk: {simulation['average_r']:.2f}R")
            for item in simulation["items"][:3]:
                entry_txt = _fmt_price(item.get("entry"))
                tp_txt = _fmt_signed(item.get("pnl_tp"))
                sl_txt = _fmt_signed(item.get("pnl_sl"))
                r_txt = f", R {item['r_multiple']:.2f}" if item.get("r_multiple") is not None else ""
                plain_lines.append(
                    f"  * {item.get('ticker', '?')} {item.get('side', '?')} @ {entry_txt} -> TP {tp_txt} / SL {sl_txt}{r_txt}"
                )
        else:
            plain_lines.append("- No trade plans were logged yesterday.")
        plain_lines.append("")
        plain_lines.append("Fresh trade ideas:")
        if rows:
            for row in rows:
                plain_lines.append(self.describe_decision(row))
        else:
            plain_lines.append("- No new trade ideas yet.")
        plain_lines.append("")
        plain_lines.append("Next steps:")
        plain_lines.append("1. Pick the setups that match your plan and size the position from the stop distance.")
        plain_lines.append("2. Update your journal once orders are placed or skipped.")
        plain_lines.append("")
        plain_lines.append("Glossary:")
        plain_lines.append("- ATR: measures recent price movement; larger ATR implies smaller position size.")
        plain_lines.append("- Stop-loss: exit level that caps risk if price moves against the trade.")
        plain_lines.append("- Take-profit: exit level that locks in gains when price reaches the objective.")
        plain_lines.append("- R-multiple: reward divided by risk, used to compare setups.")
        plain_lines.append("")
        plain_lines.append("Questions? Reply to this email and we will help.")

        plain_text = "
".join(plain_lines)

        css = """
        <style>
        body {background:#f4f6fb;font-family:Segoe UI,Arial,sans-serif;color:#0f172a;margin:0;padding:24px;}
        .wrapper {max-width:720px;margin:auto;background:#ffffff;border-radius:16px;padding:32px;box-shadow:0 22px 40px rgba(15,23,42,0.12);}
        h2 {margin-top:0;font-weight:700;color:#0f172a;}
        .section {margin-bottom:24px;}
        .card {background:#f8fafc;border-radius:12px;padding:16px;margin-top:12px;}
        .muted {color:#64748b;font-size:14px;}
        .list li {margin-bottom:8px;}
        .steps li {margin-bottom:6px;}
        .footer {font-size:12px;color:#64748b;margin-top:32px;}
        </style>
        """

        snapshot_html = (
            "<div class='card'><strong>Closed trades yesterday</strong>"
            f"<p class='muted'>Total {snapshot['total']} | Wins {snapshot['wins']} | Losses {snapshot['losses']} | Still open {snapshot['open']} | Net P/L {snapshot['pnl']:+.2f}</p></div>"
        ) if snapshot else "<div class='card'><strong>Closed trades yesterday</strong><p class='muted'>No trades were closed yesterday.</p></div>"

        chart_html = (
            "<div class='card'><strong>Yesterday chart</strong><br /><img src='cid:daily_chart' alt='Yesterday results chart' style='max-width:360px;border-radius:8px;margin-top:8px;'/></div>"
            if chart_path
            else "<div class='card'><strong>Yesterday chart</strong><p class='muted'>No closed trades yesterday.</p></div>"
        )

        if simulation and simulation.get("count", 0) > 0:
            sim_summary_parts = [
                f"<p class='muted'>Plans logged: {simulation['count']} (with both exits: {simulation['count_with_levels']})</p>",
                f"<p class='muted'>If every target filled: {simulation['total_tp']:+.2f}</p>",
            ]
            if simulation.get("count_with_levels", 0) > 0:
                sim_summary_parts.append(f"<p class='muted'>If every stop triggered: {simulation['total_sl']:+.2f}</p>")
            if simulation.get("average_r") is not None:
                sim_summary_parts.append(f"<p class='muted'>Average reward-to-risk: {simulation['average_r']:.2f}R</p>")
            sim_summary_html = "".join(sim_summary_parts)
            item_rows: list[str] = []
            for item in simulation["items"][:4]:
                entry_txt = _fmt_price(item.get("entry"))
                tp_txt = _fmt_signed(item.get("pnl_tp"))
                sl_txt = _fmt_signed(item.get("pnl_sl"))
                r_txt = f" | R {item['r_multiple']:.2f}" if item.get("r_multiple") is not None else ""
                item_rows.append(
                    f"<li><strong>{item.get('ticker', '?')}</strong> {item.get('side', '?')} @ {entry_txt} <span class='muted'>TP {tp_txt} | SL {sl_txt}{r_txt}</span></li>"
                )
            simulation_items_html = "".join(item_rows) or "<li>No trade plans were logged yesterday.</li>"
            simulation_block = f"<div class='card'><strong>Simulated execution</strong>{sim_summary_html}<ul class='list'>{simulation_items_html}</ul></div>"
        else:
            simulation_block = "<div class='card'><strong>Simulated execution</strong><p class='muted'>No trade plans were logged yesterday.</p></div>"

        ideas_html = "".join(
            f"<li><strong>{row.get('ticker', '?')}</strong> {FRIENDLY_SIDE.get(row.get('side', ''), row.get('side', ''))} near {row.get('price', '?')} <span class='muted'>Stop {row.get('sl', '-')} | Target {row.get('tp', '-')} | Timeframe {row.get('interval', '1d')} | ADX {row.get('adx', '?')}</span></li>"
            for row in rows
        ) if rows else "<li>No new trade ideas yet.</li>"

        html = f"""
        <html>
          <head><meta charset='utf-8'/>{css}</head>
          <body>
            <div class='wrapper'>
              <h2>Daily Trading Digest - {now}</h2>
              <div class='section'>
                <div class='card'><strong>Lifetime totals</strong><p class='muted'>Wins {stats.get('wins',0)} | Losses {stats.get('losses',0)} | Open {stats.get('open',0)}</p></div>
                {snapshot_html}
                {chart_html}
                {simulation_block}
              </div>
              <div class='section'>
                <p><strong>Fresh trade ideas</strong></p>
                <ul class='list'>{ideas_html}</ul>
              </div>
              <div class='section'>
                <p><strong>Next steps</strong></p>
                <ol class='steps'>
                  <li>Pick the setups that match your plan and size the position from the stop distance.</li>
                  <li>Update your journal once orders are placed or skipped.</li>
                </ol>
              </div>
              <div class='section'>
                <p><strong>Glossary</strong></p>
                <ul class='list'>
                  <li><strong>ATR</strong>: measures recent price movement; larger ATR implies smaller position size.</li>
                  <li><strong>Stop-loss</strong>: exit level that caps risk if price moves against the trade.</li>
                  <li><strong>Take-profit</strong>: exit level that locks in gains when price reaches the objective.</li>
                  <li><strong>R-multiple</strong>: reward divided by risk, used to compare setups.</li>
                </ul>
              </div>
              <p class='footer'>Questions? Reply to this email and we will help.</p>
            </div>
          </body>
        </html>
        """

        return plain_text, html, chart_path

    def build_telegram_message(self, decisions: int = 3) -> str:
        now = dt.datetime.now().strftime("%d %b %H:%M")
        stats = self.trade_stats()
        rows = self.latest_decisions(decisions)
        snapshot = self.yesterday_snapshot()
        simulation = self.simulate_recommended_trades()

        lines = [f"Trading Digest {now}"]
        lines.append(
            f"Wins {stats.get('wins', 0)} | Losses {stats.get('losses', 0)} | Open {stats.get('open', 0)}"
        )
        if snapshot:
            lines.append(
                f"Closed yesterday: {snapshot['total']} | Net P/L {snapshot['pnl']:+.2f}"
            )
        else:
            lines.append("Closed yesterday: none")
        if simulation and simulation.get("count", 0) > 0:
            lines.append(f"Simulated TP: {simulation['total_tp']:+.2f}")
            if simulation.get("count_with_levels", 0) > 0:
                lines.append(f"Simulated SL: {simulation['total_sl']:+.2f}")
        lines.append("Ideas:")
        if rows:
            for row in rows:
                ticker = row.get("ticker", "?")
                side = row.get("side", "Hold")
                price = row.get("price", "?")
                sl = row.get("sl", "-")
                tp = row.get("tp", "-")
                lines.append(f"- {ticker} {side} @ {price} (SL {sl} / TP {tp})")
        else:
            lines.append("- No new trade ideas yet.")
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

