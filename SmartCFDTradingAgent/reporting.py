from __future__ import annotations

import datetime as dt
import json
import csv
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
            df = pd.read_csv(trade_log)
        except Exception:
            return None
        if df.empty or "time" not in df.columns:
            return None

        today = dt.datetime.now().date()
        yday = today - dt.timedelta(days=1)
        df = df.dropna(subset=["time"])
        df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True, format="ISO8601")
        df = df.dropna(subset=["time"])
        try:
            local_times = df["time"].dt.tz_convert(self.timezone)
        except Exception:
            local_times = df["time"].dt.tz_convert("UTC")
        df["date"] = local_times.dt.date
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
            df = pd.read_csv(decision_log, engine="python")
        except Exception:
            try:
                with decision_log.open("r", encoding="utf-8") as handle:
                    rows = list(csv.DictReader(handle))
            except Exception:
                return None
            if not rows:
                return None
            df = pd.DataFrame(rows)
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
        rows = self.latest_decisions(decisions)
        target_date = dt.datetime.now().date() - dt.timedelta(days=1)
        simulation = self.simulate_recommended_trades(target_date)
        self.backfill_simulated_crypto_trades(target_date, simulation)
        stats = self.trade_stats()
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
        plain_lines.extend(
            [
                f"Daily Trading Digest | {now}",
                "=" * 72,
                "",
                "AT A GLANCE",
                f"- Scoreboard: Wins {stats.get('wins', 0)}, losses {stats.get('losses', 0)}, open {stats.get('open', 0)}",
            ]
        )
        if snapshot:
            plain_lines.append(
                f"- Yesterday: {snapshot['total']} trades closed (wins {snapshot['wins']}, losses {snapshot['losses']}, still open {snapshot['open']})"
            )
            plain_lines.append(f"- Net change: {snapshot['pnl']:+.2f}")
        else:
            plain_lines.append("- Yesterday: no trades were closed.")
        plain_lines.append("- Trend note: ATR keeps risk steady — higher ATR automatically means smaller position size.")

        plain_lines.append("")
        plain_lines.append("PLAN REVIEW")
        if simulation and simulation.get("count", 0) > 0:
            plain_lines.append(
                f"- Plans reviewed: {simulation['count']} (full levels set: {simulation['count_with_levels']})"
            )
            total_tp = simulation.get("total_tp")
            move_text = _fmt_signed(total_tp) if total_tp is not None else "n/a"
            plain_lines.append(f"- Targets move: {move_text}")
            if simulation.get("total_risk") is not None:
                plain_lines.append(f"- Distance to stops: {simulation['total_risk']:.2f}")
            if simulation.get("reward_to_risk_ratio") is not None:
                plain_lines.append(
                    f"- Reward vs risk: {simulation['reward_to_risk_ratio']:.2f}"
                )
            if simulation.get("breakeven_win_rate") is not None:
                plain_lines.append(
                    f"- Break-even win rate: {simulation['breakeven_win_rate']:.2f}%"
                )
        else:
            plain_lines.append("- No trade plans were logged yesterday.")

        plain_lines.append("")
        plain_lines.append("FRESH TRADE IDEAS")
        if rows:
            for row in rows:
                plain_lines.append(
                    f"- {row.get('ticker', '?')}: {row.get('side','?')} near {row.get('price','?')} | stop {row.get('sl','-')} | target {row.get('tp','-')} | timeframe {row.get('interval','1d')} | trend guide {row.get('adx','?')}"
                )
        else:
            plain_lines.append("- No new ideas yet. We'll share as soon as something qualifies.")

        plain_lines.append("")
        plain_lines.append("NEXT STEPS")
        plain_lines.append("1. Open your broker and place any ideas you like (with stop & target).")
        plain_lines.append("2. Keep a one-line note explaining why you traded or passed.")

        plain_lines.append("")
        plain_lines.append("GLOSSARY")
        plain_lines.append("- ATR: measures typical price movement; bigger ATR means smaller position size.")
        plain_lines.append("- Stop-loss: automatic exit if price moves against us.")
        plain_lines.append("- Target: automatic exit when price hits the goal.")
        plain_lines.append("- ADX: trend strength indicator; higher values usually mean a stronger trend.")

        plain_lines.append("")
        plain_lines.append("Questions? Reply to this email and we'll help you out.")

        plain_text = "\n".join(plain_lines)

        css = """
        <style>
        :root { color-scheme: light; }
        body { margin:0; background:#eef2f8; font-family:'Segoe UI', Arial, sans-serif; color:#0f172a; }
        .container { max-width:720px; margin:40px auto; background:#ffffff; border-radius:24px; padding:0 0 36px; box-shadow:0 30px 60px rgba(15,23,42,0.12); overflow:hidden; }
        .header { padding:32px 36px; background:linear-gradient(120deg,#0f172a,#1d4ed8); color:#f8fafc; display:flex; gap:18px; align-items:center; }
        .header-icon { width:48px; height:48px; border-radius:16px; background:rgba(255,255,255,0.12); display:flex; align-items:center; justify-content:center; font-size:26px; }
        .badge { display:inline-block; padding:4px 12px; background:rgba(255,255,255,0.18); border-radius:999px; font-size:11px; letter-spacing:0.14em; text-transform:uppercase; font-weight:600; }
        .header-text { flex:1; }
        .header-text h1 { margin:6px 0 6px; font-size:26px; font-weight:700; letter-spacing:0.01em; }
        .header-text p { margin:0; font-size:14px; opacity:0.85; }
        .content { padding:28px 36px 0; }
        .section { background:#f8fafc; border:1px solid #e2e8f0; border-radius:18px; padding:20px 24px; margin-bottom:20px; }
        .section h2 { margin:0 0 14px; font-size:15px; letter-spacing:0.12em; text-transform:uppercase; color:#475569; }
        .section p { margin:0 0 10px; font-size:14px; line-height:1.55; color:#1f2937; }
        .section ul { margin:0; padding-left:20px; }
        .section li { margin-bottom:8px; font-size:14px; line-height:1.55; color:#1f2937; }
        .summary-cards { display:grid; gap:16px; grid-template-columns:repeat(auto-fit, minmax(210px, 1fr)); }
        .summary-card { display:flex; gap:12px; align-items:flex-start; background:#ffffff; border-radius:16px; padding:16px 18px; border:1px solid #e2e8f0; box-shadow:0 10px 25px rgba(15,23,42,0.06); }
        .summary-card .icon { width:36px; height:36px; border-radius:12px; background:#eef2ff; display:flex; align-items:center; justify-content:center; font-size:20px; }
        .summary-card strong { display:block; font-size:15px; color:#1e293b; margin-bottom:4px; }
        .summary-card span { font-size:14px; color:#334155; line-height:1.5; display:block; }
        .plan-list { list-style:none; padding:0; margin:0; display:grid; gap:10px; }
        .plan-list li { background:#ffffff; border-radius:14px; border:1px dashed #c7d2fe; padding:12px 14px; }
        .plan-list strong { display:block; font-size:14px; color:#4338ca; margin-bottom:2px; letter-spacing:0.08em; text-transform:uppercase; }
        .idea-list { list-style:none; padding:0; margin:0; display:grid; gap:12px; }
        .idea-list li { background:#ffffff; border-radius:14px; border:1px solid #dbeafe; padding:14px 16px; box-shadow:0 12px 24px rgba(37,99,235,0.08); }
        .idea-list strong { font-size:15px; color:#1d4ed8; }
        .idea-meta { display:flex; flex-wrap:wrap; gap:8px 14px; margin-top:6px; font-size:13px; color:#334155; }
        .idea-meta span { display:flex; align-items:center; gap:6px; background:#eef4ff; padding:4px 10px; border-radius:999px; }
        .chart { text-align:center; }
        .chart img { max-width:100%; border-radius:16px; border:1px solid #dbeafe; background:#ffffff; box-shadow:0 16px 32px rgba(15,23,42,0.12); }
        .chart p { margin:0; font-size:13px; color:#475569; }
        .glossary { columns:2; column-gap:28px; }
        .glossary li { break-inside:avoid; }
        .footer { margin:12px 36px 0; font-size:13px; color:#64748b; text-align:center; }
        @media only screen and (max-width:600px) {
          .container { margin:0; border-radius:0; padding-bottom:24px; }
          .header { padding:24px; border-radius:0; }
          .content { padding:24px 20px 0; }
          .summary-cards { grid-template-columns:1fr; }
          .glossary { columns:1; }
        }
        </style>
        """

        summary_cards = [
            (
                "✅",
                "Scoreboard",
                f"Wins {stats.get('wins', 0)} · Losses {stats.get('losses', 0)} · Open {stats.get('open', 0)}",
            ),
            (
                "📆",
                "Yesterday",
                f"{snapshot['total']} closed | Net {snapshot['pnl']:+.2f}" if snapshot else "No trades were closed.",
            ),
            (
                "📊",
                "Trend note",
                "ATR keeps risk steady — larger ATR automatically sizes positions smaller.",
            ),
        ]
        summary_html = (
            "<section class='section'><h2>At a Glance</h2><div class='summary-cards'>"
            + "".join(
                f"<div class='summary-card'><div class='icon'>{icon}</div><div><strong>{title}</strong><span>{body}</span></div></div>"
                for icon, title, body in summary_cards
            )
            + "</div></section>"
        )

        plan_points: list[str] = []
        if simulation and simulation.get("count", 0) > 0:
            plan_points.append(
                f"<li><strong>Plans reviewed</strong>{simulation['count']} (full levels {simulation['count_with_levels']})</li>"
            )
            total_tp = simulation.get("total_tp")
            if total_tp is not None:
                plan_points.append(f"<li><strong>Targets move</strong>{_fmt_signed(total_tp)}</li>")
            total_risk = simulation.get("total_risk")
            if total_risk is not None:
                plan_points.append(f"<li><strong>Distance to stops</strong>{float(total_risk):.2f}</li>")
            reward_rr = simulation.get("reward_to_risk_ratio")
            if reward_rr is not None:
                plan_points.append(f"<li><strong>Reward vs risk</strong>{float(reward_rr):.2f}</li>")
            break_even = simulation.get("breakeven_win_rate")
            if break_even is not None:
                plan_points.append(f"<li><strong>Break-even win rate</strong>{float(break_even):.2f}%</li>")
        else:
            plan_points.append(
                "<li><strong>Plans reviewed</strong>No trade plans were logged yesterday.</li>"
            )
        plan_html = (
            "<section class='section'><h2>Plan Review</h2><ul class='plan-list'>"
            + "".join(plan_points)
            + "</ul></section>"
        )

        if rows:
            idea_rows: list[str] = []
            for row in rows:
                idea_rows.append(
                    "<li>"
                    f"<strong>{row.get('ticker','?')}</strong> {row.get('side','?')} · TF {row.get('interval','1d')}"
                    "<div class='idea-meta'>"
                    f"<span>💰 Entry {_fmt_price(row.get('price'))}</span>"
                    f"<span>🛡 Stop {_fmt_price(row.get('sl'))}</span>"
                    f"<span>🎯 Target {_fmt_price(row.get('tp'))}</span>"
                    f"<span>📈 ADX {row.get('adx','?')}</span>"
                    "</div></li>"
                )
            ideas_html = (
                "<section class='section'><h2>Fresh Trade Ideas</h2><ul class='idea-list'>"
                + "".join(idea_rows)
                + "</ul></section>"
            )
        else:
            ideas_html = (
                "<section class='section'><h2>Fresh Trade Ideas</h2><p>No new trade ideas yet. We will signal as soon as a setup qualifies.</p></section>"
            )

        chart_html = (
            "<section class='section chart'><h2>Yesterday's Activity</h2><img src='cid:daily_chart' alt='Yesterday results chart'/><p>Closed trades performance snapshot</p></section>"
            if chart_path
            else "<section class='section chart'><h2>Yesterday's Activity</h2><p>No trades were closed yesterday, so there is no chart to share.</p></section>"
        )

        steps_html = """
        <section class='section'><h2>Next Steps</h2><ol>
          <li>Open your broker and place any ideas you like (with stop &amp; target).</li>
          <li>Keep a one-line note explaining why you traded or passed.</li>
        </ol></section>
        """

        glossary_html = """
        <section class='section'><h2>Word Bank (Glossary)</h2><ul class='glossary'>
          <li><strong>ATR:</strong> measures typical price movement; bigger ATR means smaller position size.</li>
          <li><strong>Stop-loss:</strong> automatic exit if price moves against us.</li>
          <li><strong>Target:</strong> automatic exit when price hits the goal.</li>
          <li><strong>ADX:</strong> trend strength indicator; higher values usually mean a stronger trend.</li>
        </ul></section>
        """

        footer_html = "<p class='footer'>Questions? Reply to this email and we'll help you out.</p>"

        html = f"""
        <html>
          <head><meta charset='utf-8'/>{css}</head>
          <body>
            <div class='container'>
              <div class='header'>
                <div class='header-icon'>📈</div>
                <div class='header-text'>
                  <span class='badge'>Market Snapshot</span>
                  <h1>Daily Trading Digest</h1>
                  <p>{now}</p>
                </div>
              </div>
              <div class='content'>
                {summary_html}
                {plan_html}
                {ideas_html}
                {chart_html}
                {steps_html}
                {glossary_html}
              </div>
              {footer_html}
            </div>
          </body>
        </html>
        """

        return plain_text, html, chart_path
    def build_telegram_message(self, decisions: int = 3) -> str:
        now = dt.datetime.now().strftime("%d %b %H:%M")
        rows = self.latest_decisions(decisions)
        target_date = dt.datetime.now().date() - dt.timedelta(days=1)
        simulation = self.simulate_recommended_trades(target_date)
        self.backfill_simulated_crypto_trades(target_date, simulation)
        stats = self.trade_stats()
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












