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
        plain_lines.append(f"🌅 Daily Trading Digest - {now}")
        plain_lines.append("")
        plain_lines.append("Yesterday at a glance")
        plain_lines.append(
            f"- All-time totals: {stats.get('wins', 0)} wins | {stats.get('losses', 0)} losses | {stats.get('open', 0)} open"
        )
        if snapshot:
            plain_lines.append(
                f"- Trades closed: {snapshot['total']} (wins {snapshot['wins']}, losses {snapshot['losses']}, still open {snapshot['open']})"
            )
            plain_lines.append(f"- Net change: {snapshot['pnl']:+.2f}")
        else:
            plain_lines.append("- No trades were closed yesterday.")

        plain_lines.append("")
        plain_lines.append("If every plan hit its targets")
        if simulation and simulation.get("count", 0) > 0:
            plain_lines.append(
                f"- Plans reviewed: {simulation['count']} (with full levels set: {simulation['count_with_levels']})"
            )
            plain_lines.append(f"- Potential gain at targets: {simulation['total_tp']:+.2f}")
            if simulation.get("total_risk") is not None:
                plain_lines.append(f"- Distance to safety nets (stops): {simulation['total_risk']:.2f}")
            if simulation.get("total_reward") is not None:
                plain_lines.append(f"- Distance to targets: {simulation['total_reward']:.2f}")
            if simulation.get("reward_to_risk_ratio") is not None:
                plain_lines.append(
                    f"- Reward vs. risk ratio: {simulation['reward_to_risk_ratio']:.2f}"
                )
            if simulation.get("breakeven_win_rate") is not None:
                plain_lines.append(
                    f"- Win rate needed to break even: {simulation['breakeven_win_rate']:.2f}%"
                )
            for item in simulation["items"][:3]:
                entry_txt = _fmt_price(item.get("entry"))
                tp_txt = _fmt_signed(item.get("pnl_tp"))
                sl_txt = _fmt_signed(item.get("pnl_sl"))
                r_txt = f", R {item['r_multiple']:.2f}" if item.get("r_multiple") is not None else ""
                plain_lines.append(
                    f"   -> {item.get('ticker', '?')} {item.get('side', '?')} near {entry_txt} (target move {tp_txt}, stop move {sl_txt}{r_txt})"
                )
        else:
            plain_lines.append("- No trade plans were logged yesterday.")

        plain_lines.append("")
        plain_lines.append("Fresh ideas on the radar")
        if rows:
            for row in rows:
                plain_lines.append(
                    f"- {row.get('ticker', '?')}: {row.get('side','?')} near {row.get('price','?')} | stop {row.get('sl','-')} | target {row.get('tp','-')} | timeframe {row.get('interval','1d')} | trend guide {row.get('adx','?')}"
                )
        else:
            plain_lines.append("- No new ideas yet. We'll share as soon as something qualifies.")

        plain_lines.append("")
        plain_lines.append("Quick actions")
        plain_lines.append("1. Pick the setups that match your plan and size positions from the stop distance.")
        plain_lines.append("2. Make a quick note explaining why you chose to trade or pass.")

        plain_lines.append("")
        plain_lines.append("Word bank (Glossary)")
        plain_lines.append("- Stop-loss: a pre-set exit that limits how much the trade can hurt you.")
        plain_lines.append("- Target: a price where we choose to lock in gains.")
        plain_lines.append("- Reward vs. risk: how much the idea could earn compared with what it could lose.")
        plain_lines.append("- Trend guide (ADX): a number showing how strong the price move is right now.")

        plain_lines.append("")
        plain_lines.append("Questions? Reply to this email and we will help.")

        plain_text = "\n".join(plain_lines)

        css = """
        <style>
        body {{background:#eef2ff;font-family:'Segoe UI',Arial,sans-serif;color:#0f172a;margin:0;padding:24px;}}
        .wrapper {{max-width:760px;margin:auto;background:#ffffff;border-radius:24px;padding:36px;box-shadow:0 30px 60px rgba(15,23,42,0.12);}}
        .hero {{background:linear-gradient(135deg,#2563eb,#22d3ee);color:#ffffff;padding:28px;border-radius:20px;display:flex;flex-direction:column;gap:4px;}}
        .hero__title {{font-size:26px;font-weight:700;}}
        .hero__subtitle {{font-size:16px;opacity:0.9;}}
        .grid {{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:16px;margin:28px 0;}}
        .card {{background:#f8fafc;border-radius:18px;padding:20px;box-shadow:0 16px 32px rgba(15,23,42,0.08);border:1px solid rgba(148,163,184,0.2);}}
        .metric__icon {{font-size:24px;margin-bottom:12px;}}
        .metric__title {{font-size:14px;font-weight:600;text-transform:uppercase;color:#475569;letter-spacing:0.05em;}}
        .metric__value {{font-size:20px;font-weight:700;color:#0f172a;margin-top:6px;}}
        .section {{margin-bottom:28px;}}
        .section h3 {{margin:0 0 12px;font-size:20px;color:#0f172a;}}
        .summary-list {{list-style:none;margin:0;padding:0;display:grid;gap:10px;}}
        .summary-list li {{background:#eef2ff;border-radius:14px;padding:12px 14px;font-size:15px;color:#1e293b;}}
        .ideas {{display:grid;gap:14px;}}
        .idea-card {{border-radius:16px;padding:16px 18px;background:#ffffff;border:1px solid rgba(148,163,184,0.35);box-shadow:0 12px 24px rgba(15,23,42,0.06);}}
        .idea-card h4 {{margin:0 0 6px;font-size:16px;}}
        .idea-card p {{margin:0;font-size:14px;color:#475569;}}
        .badge {{display:inline-block;background:#e0f2fe;color:#0369a1;border-radius:999px;padding:4px 10px;font-size:12px;margin-left:6px;}}
        .chart-card img {{max-width:100%;border-radius:14px;margin-top:12px;}}
        .steps li {{margin-bottom:8px;}}
        .word-bank {{display:grid;gap:10px;margin-top:12px;}}
        .word-bank .term {{background:#f1f5f9;padding:12px;border-radius:12px;color:#1e293b;font-size:14px;}}
        .footer {{margin-top:32px;font-size:13px;color:#64748b;text-align:center;}}
        </style>
        """

        lifetime_html = (
            f"<div class='card metric'><div class='metric__icon'>ðŸ“Š</div><div class='metric__title'>All-time score</div><div class='metric__value'>{stats.get('wins',0)} wins | {stats.get('losses',0)} losses | {stats.get('open',0)} open</div></div>"
        )
        if snapshot:
            yesterday_value = f"{snapshot['total']} closed | net {snapshot['pnl']:+.2f}"
        else:
            yesterday_value = "No trades closed yesterday"
        yesterday_html = (
            f"<div class='card metric'><div class='metric__icon'>ðŸ•’</div><div class='metric__title'>Yesterday</div><div class='metric__value'>{yesterday_value}</div></div>"
        )
        if simulation and simulation.get("count", 0) > 0:
            safety = simulation.get('total_risk', 0.0)
            potential_value = f"Targets {simulation['total_tp']:+.2f} | Stops {safety:.2f}"
        else:
            potential_value = "No plans logged"
        simulation_metric_html = (
            f"<div class='card metric'><div class='metric__icon'>ðŸ§­</div><div class='metric__title'>Plan check</div><div class='metric__value'>{potential_value}</div></div>"
        )

        grid_html = f"<section class='grid'>{lifetime_html}{yesterday_html}{simulation_metric_html}</section>"

        summary_items: list[str] = []
        if simulation and simulation.get("count", 0) > 0:
            summary_items.append(
                f"<li>Plans reviewed: {simulation['count']} (full levels: {simulation['count_with_levels']})</li>"
            )
            summary_items.append(f"<li>Potential gain at targets: {simulation['total_tp']:+.2f}</li>")
            if simulation.get("total_risk") is not None:
                summary_items.append(f"<li>Safety net distance (stops): {simulation['total_risk']:.2f}</li>")
            if simulation.get("total_reward") is not None:
                summary_items.append(f"<li>Distance to targets: {simulation['total_reward']:.2f}</li>")
            if simulation.get("reward_to_risk_ratio") is not None:
                summary_items.append(
                    f"<li>Reward vs. risk ratio: {simulation['reward_to_risk_ratio']:.2f}</li>"
                )
            if simulation.get("breakeven_win_rate") is not None:
                summary_items.append(
                    f"<li>Win rate needed to break even: {simulation['breakeven_win_rate']:.2f}%</li>"
                )
        else:
            summary_items.append("<li>No trade plans were logged yesterday.</li>")

        sim_list_html = "".join(summary_items)

        featured_items: list[str] = []
        if simulation and simulation.get("items"):
            for item in simulation["items"][:4]:
                entry_txt = _fmt_price(item.get("entry"))
                tp_txt = _fmt_signed(item.get("pnl_tp"))
                sl_txt = _fmt_signed(item.get("pnl_sl"))
                r_txt = f" Â· R {item['r_multiple']:.2f}" if item.get("r_multiple") is not None else ""
                featured_items.append(
                    f"<li>{item.get('ticker','?')} {item.get('side','?')} near {entry_txt} <span class='muted'>Target move {tp_txt} Â· Stop move {sl_txt}{r_txt}</span></li>"
                )
        featured_html = "".join(featured_items)
        if featured_html:
            featured_html = f"<ul class='summary-list'>{featured_html}</ul>"

        simulation_block = f"""
        <section class='section'>
          <h3>What the plans suggest</h3>
          <ul class='summary-list'>{sim_list_html}</ul>
          {featured_html}
        </section>
        """

        if chart_path:
            chart_html = f"<div class='card chart-card'><h3>Yesterday's picture</h3><p class='muted'>Visual snapshot of wins, losses, and open trades.</p><img src='cid:daily_chart' alt='Yesterday results chart'/></div>"
        else:
            chart_html = "<div class='card chart-card'><h3>Yesterday's picture</h3><p class='muted'>No trades were closed yesterday, so there is no chart to share.</p></div>"

        if rows:
            ideas_cards = []
            for row in rows:
                badge = f"<span class='badge'>{row.get('interval','1d')} timeframe</span>"
                ideas_cards.append(
                    f"<div class='idea-card'><h4>{row.get('ticker','?')} Â· {row.get('side','?')} {badge}</h4>"
                    f"<p>Price near {row.get('price','?')}. Stop {row.get('sl','-')} Â· Target {row.get('tp','-')} Â· Trend guide {row.get('adx','?')}.</p></div>"
                )
            ideas_html = "".join(ideas_cards)
        else:
            ideas_html = "<div class='idea-card'><p>No new trade ideas yet. We will signal as soon as a setup qualifies.</p></div>"

        steps_html = """
        <section class='section'>
          <h3>Quick actions</h3>
          <ol class='steps'>
            <li>Pick the setups that fit your plan and size the trade from the stop distance.</li>
            <li>Write a one-line note on why you traded or passed. Future you will thank you.</li>
          </ol>
        </section>
        """

        glossary_html = """
        <section class='section'>
          <h3>Word bank (Glossary)</h3>
          <div class='word-bank'>
            <div class='term'><strong>Stop-loss:</strong> pre-set exit that limits the loss.</div>
            <div class='term'><strong>Target:</strong> price where we choose to lock in gains.</div>
            <div class='term'><strong>Reward vs. risk:</strong> how much the idea could earn compared with what it could lose.</div>
            <div class='term'><strong>Trend guide (ADX):</strong> number showing how strong the current price move is.</div>
          </div>
        </section>
        """

        hero_html = f"<header class='hero'><div class='hero__title'>🌅 Daily Trading Digest</div><div class='hero__subtitle'>{now}</div></header>"

        html = f"""
        <html>
          <head><meta charset='utf-8'/>{css}</head>
          <body>
            <div class='wrapper'>
              {hero_html}
              {grid_html}
              {simulation_block}
              <section class='section'>
                <h3>Yesterday's activity</h3>
                {chart_html}
              </section>
              <section class='section'>
                <h3>Fresh ideas</h3>
                <div class='ideas'>{ideas_html}</div>
              </section>
              {steps_html}
              {glossary_html}
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
        target_date = dt.datetime.now().date() - dt.timedelta(days=1)
        simulation = self.simulate_recommended_trades(target_date)
        self.backfill_simulated_crypto_trades(target_date, simulation)
        snapshot = self.yesterday_snapshot()

        lines = [f"🌅 Daily Digest {now}"]
        lines.append(
            f"Totals â–¸ wins {stats.get('wins', 0)}, losses {stats.get('losses', 0)}, open {stats.get('open', 0)}"
        )
        if snapshot:
            lines.append(
                f"Yesterday â–¸ {snapshot['total']} closed, net {snapshot['pnl']:+.2f}"
            )
        else:
            lines.append("Yesterday â–¸ no trades were closed")

        if simulation and simulation.get("count", 0) > 0:
            lines.append(
                f"Plans â–¸ {simulation['count']} checked (full levels {simulation['count_with_levels']})"
            )
            lines.append(f"Targets â–¸ {simulation['total_tp']:+.2f}")
            if simulation.get("total_risk") is not None:
                lines.append(f"Stops â–¸ {simulation['total_risk']:.2f}")
            if simulation.get("reward_to_risk_ratio") is not None:
                lines.append(
                    f"Reward/Risk â–¸ {simulation['reward_to_risk_ratio']:.2f}"
                )
            if simulation.get("breakeven_win_rate") is not None:
                lines.append(
                    f"Break-even win rate â–¸ {simulation['breakeven_win_rate']:.2f}%"
                )
        else:
            lines.append("Plans â–¸ none logged yesterday")

        lines.append("Ideas")
        if rows:
            for row in rows:
                lines.append(
                    f"- {row.get('ticker','?')} {row.get('side','?')} @ {row.get('price','?')} (stop {row.get('sl','-')} | target {row.get('tp','-')})"
                )
        else:
            lines.append("- No new setups yet")

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










