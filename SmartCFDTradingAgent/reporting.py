from __future__ import annotations

import datetime as dt
import json
import statistics
from pathlib import Path
from typing import Any, Iterable, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from SmartCFDTradingAgent.pipeline import read_last_decisions, is_crypto
from SmartCFDTradingAgent.utils.trade_logger import aggregate_trade_stats, log_trade, CSV_PATH

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
                "median_r": None,
                "avg_risk": None,
                "avg_reward": None,
                "best_tp": None,
                "worst_sl": None,
                "total_reward": None,
                "total_risk": None,
                "reward_to_risk_ratio": None,
                "breakeven_win_rate": None,
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
        risk_values: list[float] = []
        reward_values: list[float] = []
        sl_values: list[float] = []

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
            if pnl_tp is not None and risk:
                r_multiple = pnl_tp / risk

            if tp is not None and sl is not None:
                count_with_levels += 1

            if pnl_tp is not None:
                total_tp += pnl_tp
                reward_values.append(pnl_tp)
            if pnl_sl is not None:
                total_sl += pnl_sl
                sl_values.append(pnl_sl)
            if r_multiple is not None:
                r_values.append(r_multiple)
            if risk is not None:
                risk_values.append(risk)

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
                    "risk": risk,
                    "decision_ts": getattr(row, "ts", None),
                    "decision_tz": getattr(row, "tz", None),
                    "atr": _to_float(getattr(row, "atr", None)),
                }
            )

        total_risk_distance = sum(risk_values) if risk_values else 0.0
        total_reward_distance = sum(reward_values) if reward_values else 0.0
        reward_to_risk_ratio = (total_reward_distance / total_risk_distance) if total_risk_distance else None
        breakeven_numerator = total_risk_distance
        breakeven_denominator = total_risk_distance + total_reward_distance
        breakeven_rate = (breakeven_numerator / breakeven_denominator * 100) if breakeven_denominator else None

        return {
            "date": target_date,
            "items": items,
            "count": int(len(subset)),
            "count_with_levels": int(count_with_levels),
            "total_tp": float(round(total_tp, 2)),
            "total_sl": float(round(total_sl, 2)),
            "average_r": float(round(sum(r_values) / len(r_values), 2)) if r_values else None,
            "median_r": float(round(statistics.median(r_values), 2)) if r_values else None,
            "avg_risk": float(round(sum(risk_values) / len(risk_values), 2)) if risk_values else None,
            "avg_reward": float(round(sum(reward_values) / len(reward_values), 2)) if reward_values else None,
            "best_tp": float(round(max(reward_values), 2)) if reward_values else None,
            "worst_sl": float(round(min(sl_values), 2)) if sl_values else None,
            "total_reward": float(round(total_reward_distance, 2)) if total_reward_distance else None,
            "total_risk": float(round(total_risk_distance, 2)) if total_risk_distance else None,
            "reward_to_risk_ratio": float(round(reward_to_risk_ratio, 2)) if reward_to_risk_ratio else None,
            "breakeven_win_rate": float(round(breakeven_rate, 2)) if breakeven_rate is not None else None,
        }


    def backfill_simulated_crypto_trades(
        self,
        target_date: Optional[dt.date] | None = None,
        simulation: Optional[dict[str, Any]] = None,
    ) -> int:
        """Persist simulated crypto trades into the trade log for metrics.

        For manually executed crypto trades (no broker integration), we assume the
        recommended take-profit was hit so the digest can display hypothetical
        results. Entries are tagged via ``broker="manual-simulated"`` so real
        executions can override them later.
        """

        target_date = target_date or (dt.datetime.now().date() - dt.timedelta(days=1))
        if simulation is None:
            simulation = self.simulate_recommended_trades(target_date)
        if not simulation or simulation.get("count", 0) == 0:
            return 0

        try:
            existing_df = pd.read_csv(CSV_PATH)
        except Exception:
            existing_df = pd.DataFrame()

        recorded_ids: set[str] = set()
        real_pairs: set[tuple[str, dt.date]] = set()
        if not existing_df.empty:
            if "order_id" in existing_df.columns:
                recorded_ids = {
                    str(x) for x in existing_df["order_id"].dropna().astype(str)
                }
            if {"ticker", "time", "broker"}.issubset(existing_df.columns):
                times = pd.to_datetime(existing_df["time"], errors="coerce")
                brokers = existing_df["broker"].fillna("").astype(str)
                tickers = existing_df["ticker"].fillna("").astype(str).str.upper()
                for ticker, ts_value, broker in zip(tickers, times, brokers):
                    if pd.isna(ts_value):
                        continue
                    day = ts_value.date()
                    if day != target_date:
                        continue
                    if broker.lower() != "manual-simulated":
                        real_pairs.add((ticker, day))

        saved = 0
        items = simulation.get("items", [])

        def _resolve_dt(value: Any, fallback_date: dt.date, offset_minutes: int) -> dt.datetime:
            if isinstance(value, dt.datetime):
                return value
            if isinstance(value, pd.Timestamp):
                if pd.isna(value):
                    pass
                else:
                    return value.to_pydatetime()
            if isinstance(value, str):
                try:
                    return dt.datetime.fromisoformat(value)
                except ValueError:
                    pass
            return dt.datetime.combine(fallback_date, dt.time(9, 0)) + dt.timedelta(minutes=offset_minutes)

        for idx, item in enumerate(items):
            ticker = str(item.get("ticker") or "").upper()
            if not ticker or not is_crypto(ticker):
                continue
            if (ticker, target_date) in real_pairs:
                continue

            entry = item.get("entry")
            tp = item.get("tp")
            if entry is None or tp is None:
                continue

            decision_dt = _resolve_dt(item.get("decision_ts"), target_date, idx)
            order_id = f"SIM-{ticker}-{decision_dt:%Y%m%d%H%M%S}-{idx}"
            if order_id in recorded_ids:
                continue

            sl = item.get("sl")
            pnl_tp = item.get("pnl_tp") or 0.0
            risk_abs = item.get("risk")
            if not risk_abs and entry is not None and sl is not None:
                try:
                    risk_abs = abs(float(entry) - float(sl))
                except (TypeError, ValueError):
                    risk_abs = None
            r_multiple = item.get("r_multiple")
            if r_multiple is None and risk_abs not in (None, 0):
                try:
                    r_multiple = float(pnl_tp) / float(risk_abs) if risk_abs else None
                except (TypeError, ValueError):
                    r_multiple = None

            trade_row = {
                "time": decision_dt.isoformat(),
                "ticker": ticker,
                "side": item.get("side"),
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "exit": tp,
                "exit_reason": "simulated_tp",
                "atr": item.get("atr"),
                "r_multiple": r_multiple,
                "fees": 0.0,
                "broker": "manual-simulated",
                "order_id": order_id,
            }

            try:
                log_trade(trade_row)
            except Exception:
                continue

            recorded_ids.add(order_id)
            saved += 1

        return saved

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
        target_date = dt.datetime.now().date() - dt.timedelta(days=1)
        simulation = self.simulate_recommended_trades(target_date)
        self.backfill_simulated_crypto_trades(target_date, simulation)
        snapshot = self.yesterday_snapshot()
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
        plain_lines.extend([
            f"Daily Trading Digest | {now}",
            "=" * 72,
            "",
            "Scoreboard",
            f"- Wins {stats.get('wins', 0)}, losses {stats.get('losses', 0)}, open {stats.get('open', 0)}",
        ])
        if snapshot:
            plain_lines.append(
                f"- Yesterday: {snapshot['total']} trades closed (wins {snapshot['wins']}, losses {snapshot['losses']}, still open {snapshot['open']})"
            )
            plain_lines.append(f"- Net change: {snapshot['pnl']:+.2f}")
        else:
            plain_lines.append("- Yesterday: no trades were closed.")

        plain_lines.append("")
        plain_lines.append("If plans ran as drawn")
        if simulation and simulation.get("count", 0) > 0:
            plain_lines.append(
                f"- Plans reviewed: {simulation['count']} (full levels set: {simulation['count_with_levels']})"
            )
            plain_lines.append(f"- Potential move at targets: {simulation['total_tp']:+.2f}")
            if simulation.get("total_risk") is not None:
                plain_lines.append(f"- Distance to stops: {simulation['total_risk']:.2f}")
            if simulation.get("reward_to_risk_ratio") is not None:
                plain_lines.append(
                    f"- Reward vs risk ratio: {simulation['reward_to_risk_ratio']:.2f}"
                )
            if simulation.get("breakeven_win_rate") is not None:
                plain_lines.append(
                    f"- Break-even win rate: {simulation['breakeven_win_rate']:.2f}%"
                )
        else:
            plain_lines.append("- No trade plans were logged yesterday.")

        plain_lines.append("")
        plain_lines.append("Fresh trade ideas")
        if rows:
            for row in rows:
                plain_lines.append(
                    f"- {row.get('ticker', '?')}: {row.get('side','?')} near {row.get('price','?')} | stop {row.get('sl','-')} | target {row.get('tp','-')} | timeframe {row.get('interval','1d')} | trend guide {row.get('adx','?')}"
                )
        else:
            plain_lines.append("- No new ideas yet. We'll share as soon as something qualifies.")

        plain_lines.append("")
        plain_lines.append("Next steps")
        plain_lines.append("1. Open your broker and place any ideas you like (with stop & target).")
        plain_lines.append("2. Keep a one-line note explaining why you traded or passed.")

        plain_lines.append("")
        plain_lines.append("Word bank (Glossary)")
        plain_lines.append("- ATR: measures typical price movement; bigger ATR means smaller position size.")
        plain_lines.append("- Stop-loss: automatic exit if price moves against us.")
        plain_lines.append("- Target: automatic exit when price hits the goal.")
        plain_lines.append("- ADX: trend strength indicator; higher values usually mean a stronger trend.")

        plain_lines.append("")
        plain_lines.append("Questions? Reply to this email and we'll help you out.")

        plain_text = "\n".join(plain_lines)

        css = """
        <style>
        body {{background:#edf1f8;font-family:'Segoe UI',Arial,sans-serif;color:#0f172a;margin:0;padding:0;}}
        .container {{max-width:680px;margin:36px auto;background:#ffffff;border-radius:18px;padding:28px 32px;box-shadow:0 20px 44px rgba(15,23,42,0.12);}}
        .header {{display:flex;align-items:flex-start;gap:14px;margin-bottom:18px;}}
        .header-icon {{font-size:30px;line-height:1;}}
        .header h1 {{margin:0;font-size:22px;font-weight:700;color:#111827;}}
        .header p {{margin:4px 0 0;font-size:14px;color:#475569;}}
        .summary-grid {{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:16px;}}
        .summary-card {{display:flex;gap:10px;align-items:flex-start;padding:12px 14px;border-radius:14px;background:#f6f8ff;border:1px solid rgba(99,102,241,0.18);}}
        .summary-card span.icon {{font-size:18px;margin-top:2px;}}
        .summary-card div {{font-size:14px;line-height:1.45;color:#0f172a;}}
        .section {{margin-bottom:18px;}}
        .section h2 {{margin:0 0 10px;font-size:15px;text-transform:uppercase;letter-spacing:0.08em;color:#6b7280;display:flex;align-items:center;gap:8px;}}
        .section ul {{margin:0;padding-left:18px;}}
        .section li {{margin-bottom:6px;font-size:14px;color:#1f2937;}}
        .idea-list {{list-style:none;padding-left:0;}}
        .idea-list li {{margin-bottom:10px;padding:10px 12px;border-left:4px solid #2563eb;background:#eef4ff;border-radius:10px;font-size:14px;}}
        .idea-list strong {{color:#1d4ed8;}}
        .footer {{margin-top:20px;font-size:13px;color:#64748b;text-align:center;}}
        </style>
        """

        summary_cards = []
        summary_cards.append(
            f"<div class='summary-card'><span class='icon'>✅</span><div><strong>Overall</strong><br/>Wins {stats.get('wins',0)}, losses {stats.get('losses',0)}, open {stats.get('open',0)}</div></div>"
        )
        if snapshot:
            summary_cards.append(
                f"<div class='summary-card'><span class='icon'>📆</span><div><strong>Yesterday</strong><br/>{snapshot['total']} closed | net {snapshot['pnl']:+.2f}</div></div>"
            )
        else:
            summary_cards.append(
                "<div class='summary-card'><span class='icon'>📆</span><div><strong>Yesterday</strong><br/>No trades were closed.</div></div>"
            )
        summary_cards.append(
            "<div class='summary-card'><span class='icon'>ℹ️</span><div><strong>ATR insight</strong><br/>ATR keeps risk steady — higher ATR automatically means smaller trade size.</div></div>"
        )
        summary_html = "<div class='summary-grid'>" + "".join(summary_cards) + "</div>"

        plan_items: list[str] = []
        if simulation and simulation.get("count", 0) > 0:
            plan_items.append(
                f"<li>Plans reviewed: {simulation['count']} (full levels {simulation['count_with_levels']})</li>"
            )
            plan_items.append(f"<li>Potential move at targets: {simulation['total_tp']:+.2f}</li>")
            if simulation.get("total_risk") is not None:
                plan_items.append(f"<li>Distance to stops: {simulation['total_risk']:.2f}</li>")
            if simulation.get("reward_to_risk_ratio") is not None:
                plan_items.append(
                    f"<li>Reward vs risk ratio: {simulation['reward_to_risk_ratio']:.2f}</li>"
                )
            if simulation.get("breakeven_win_rate") is not None:
                plan_items.append(
                    f"<li>Break-even win rate: {simulation['breakeven_win_rate']:.2f}%</li>"
                )
        else:
            plan_items.append("<li>No trade plans were logged yesterday.</li>")
        plan_html = "<section class='section'><h2>📌 Plan check</h2><ul>" + "".join(plan_items) + "</ul></section>"

        if rows:
            idea_items = []
            for row in rows:
                idea_items.append(
                    f"<li><strong>{row.get('ticker','?')}</strong> {row.get('side','?')} · TF {row.get('interval','1d')}<br/>Price {row.get('price','?')} · Stop {row.get('sl','-')} · Target {row.get('tp','-')} · ADX {row.get('adx','?')}</li>"
                )
            ideas_html = "<section class='section'><h2>💡 Fresh trade ideas</h2><ul class='idea-list'>" + "".join(idea_items) + "</ul></section>"
        else:
            ideas_html = "<section class='section'><h2>💡 Fresh trade ideas</h2><p>No new trade ideas yet. We will signal as soon as a setup qualifies.</p></section>"

        steps_html = """
        <section class='section'><h2>🛠 Next steps</h2><ol>
          <li>Open your broker and place any ideas you like (with stop & target).</li>
          <li>Keep a one-line note explaining why you traded or passed.</li>
        </ol></section>
        """

        glossary_html = """
        <section class='section'><h2>📘 Word bank (Glossary)</h2><ul>
          <li><strong>ATR:</strong> measures typical price movement; bigger ATR means smaller position size.</li>
          <li><strong>Stop-loss:</strong> automatic exit if price moves against us.</li>
          <li><strong>Target:</strong> automatic exit when price hits the goal.</li>
          <li><strong>ADX:</strong> trend strength indicator; higher values usually mean a stronger trend.</li>
        </ul></section>
        """

        chart_html = (
            "<section class='section'><h2>📈 Yesterday's activity</h2><img src='cid:daily_chart' alt='Yesterday results chart'/></section>"
            if chart_path
            else "<section class='section'><h2>📈 Yesterday's activity</h2><p>No trades were closed yesterday, so there is no chart to share.</p></section>"
        )

        footer_html = "<p class='footer'>Questions? Reply to this email and we'll help you out.</p>"

        html = f"""
        <html>
          <head><meta charset='utf-8'/>{css}</head>
          <body>
            <div class='container'>
              <div class='header'>
                <div class='header-icon'>📈</div>
                <div>
                  <h1>Daily Trading Digest</h1>
                  <p>{now}</p>
                </div>
              </div>
              {summary_html}
              {plan_html}
              {ideas_html}
              {chart_html}
              {steps_html}
              {glossary_html}
              {footer_html}
            </div>
          </body>
        </html>
        """

        return plain_text, html, chart_path
    def build_telegram_message(self, decisions: int = 3) -> str:
        now = dt.datetime.now().strftime("%d %b %H:%M")
        stats = self.trade_stats()
        rows = self.latest_decisions(decisions)
        target_date = dt.datetime.now().date() - dt.timedelta(days=1)
        simulation = self.simulate_recommended_trades(target_date)
        self.backfill_simulated_crypto_trades(target_date, simulation)
        snapshot = self.yesterday_snapshot()

        lines = []
        lines.append(f"DAILY TRADING DIGEST | {now}")
        lines.append("-------------------------------")
        lines.append("SCOREBOARD")
        lines.append(
            f"  Wins {stats.get('wins', 0)} | Losses {stats.get('losses', 0)} | Open {stats.get('open', 0)}"
        )
        if snapshot:
            lines.append(
                f"  Yesterday: {snapshot['total']} closed | Net {snapshot['pnl']:+.2f}"
            )
        else:
            lines.append("  Yesterday: no trades were closed")

        lines.append("")
        lines.append("PLAN CHECK")
        if simulation and simulation.get("count", 0) > 0:
            lines.append(
                f"  Plans reviewed: {simulation['count']} (full levels {simulation['count_with_levels']})"
            )
            lines.append(f"  Targets move: {simulation['total_tp']:+.2f}")
            if simulation.get("total_risk") is not None:
                lines.append(f"  Stops distance: {simulation['total_risk']:.2f}")
            if simulation.get("reward_to_risk_ratio") is not None:
                lines.append(
                    f"  Reward vs risk: {simulation['reward_to_risk_ratio']:.2f}"
                )
            if simulation.get("breakeven_win_rate") is not None:
                lines.append(
                    f"  Break-even win rate: {simulation['breakeven_win_rate']:.2f}%"
                )
        else:
            lines.append("  No trade plans were logged yesterday.")

        lines.append("")
        lines.append("IDEAS")
        if rows:
            for row in rows:
                lines.append(
                    f"  - {row.get('ticker','?')} {row.get('side','?')} @ {row.get('price','?')} (stop {row.get('sl','-')} | target {row.get('tp','-')})"
                )
        else:
            lines.append("  - No new setups yet")

        return "\n".join(lines)

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











