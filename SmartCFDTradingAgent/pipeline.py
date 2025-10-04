from __future__ import annotations

import os
import argparse
import time
import datetime as dt
import csv
import sys
import json
import yfinance as yf
import pandas as pd
from requests import HTTPError
from datetime import timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from collections import Counter
from typing import TYPE_CHECKING

from dotenv import load_dotenv

from SmartCFDTradingAgent.utils.logger import get_logger
from SmartCFDTradingAgent.utils.market_time import market_open
from SmartCFDTradingAgent.utils.telegram import send as tg_send
from SmartCFDTradingAgent.rank_assets import top_n
from SmartCFDTradingAgent.data_loader import get_price_data
from SmartCFDTradingAgent.signals import generate_signals
from SmartCFDTradingAgent.backtester import backtest
from SmartCFDTradingAgent.position import qty_from_atr
from SmartCFDTradingAgent.indicators import adx as _adx, atr as _atr
from SmartCFDTradingAgent.utils.trade_logger import log_trade

try:  # PyYAML may be missing in minimal environments
    import yaml  # type: ignore
except Exception:  # pragma: no cover - fallback for tests
    yaml = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover - hint only
    from SmartCFDTradingAgent.ml_models import PriceDirectionModel
    from SmartCFDTradingAgent.brokers.base import Broker


log = get_logger()
ROOT = Path(__file__).resolve().parent
STORE = ROOT / "storage"
STORE.mkdir(exist_ok=True)


def safe_send(msg: str) -> None:
    try:
        ok = tg_send(msg)
    except Exception as e:
        log.error("Telegram send failed: %s", e)
    else:
        if not ok:
            log.warning(
                "Telegram send returned False; message dropped (first 200 chars): %s",
                msg[:200],
            )


# --- asset classification ---
ASSET_MAP: dict[str, str] = {}


def _load_asset_classes(path: Path | None = None) -> dict[str, str]:
    path = path or ROOT / "assets.yml"
    if yaml is None or not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    mapping: dict[str, str] = {}
    if isinstance(data, dict):
        if all(isinstance(v, (list, tuple, set)) for v in data.values()):
            for cls, tickers in data.items():
                for t in tickers:
                    mapping[str(t).upper()] = str(cls)
        else:
            for t, cls in data.items():
                mapping[str(t).upper()] = str(cls)
    return mapping


ASSET_MAP = _load_asset_classes()


def classify(t: str) -> str:
    return ASSET_MAP.get((t or "").upper(), "equity")


def is_crypto(t: str) -> bool:
    return classify(t) == "crypto"


def _normalize_intervals(intervals) -> list[str]:
    if intervals is None:
        return []
    if isinstance(intervals, str):
        return [s.strip() for s in intervals.split(",") if s.strip()]
    if isinstance(intervals, (list, tuple, set)):
        out = []
        for s in intervals:
            if s is None:
                continue
            out.append(str(s).strip())
        return [s for s in out if s]
    s = str(intervals).strip()
    return [s] if s else []


def _parse_interval_weights(weights) -> dict[str, float]:
    if not weights:
        return {}
    if isinstance(weights, dict):
        out: dict[str, float] = {}
        for k, v in weights.items():
            try:
                out[str(k).strip()] = float(v)
            except (TypeError, ValueError):
                continue
        return out
    if isinstance(weights, str):
        out: dict[str, float] = {}
        for part in weights.split(","):
            if not part:
                continue
            if "=" in part:
                k, v = part.split("=", 1)
                try:
                    out[k.strip()] = float(v)
                except (TypeError, ValueError):
                    pass
        return out
    try:
        return {str(k): float(v) for k, v in dict(weights).items()}
    except Exception:
        return {}


def _max_lookback_days(iv: str) -> int:
    iv = (iv or "").lower()
    intraday = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}
    return 60 if iv in intraday else 365


# ---------- Cooldown ----------
COOL_PATH = STORE / "last_signals.json"


def _load_last_signals() -> dict:
    if not COOL_PATH.exists():
        return {}
    try:
        return json.loads(COOL_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_last_signals(d: dict) -> None:
    try:
        COOL_PATH.write_text(json.dumps(d), encoding="utf-8")
    except Exception:
        pass


def load_params() -> dict:
    p = STORE / "params.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def tuned_for(tkr: str, interval: str, key_group: str, params: dict, defaults: dict) -> dict:
    return params.get(f"{tkr}|{interval}", params.get(key_group, defaults))


def load_profile_config(path: str, profile: str) -> dict:
    """Load a profile from YAML (supports top-level or nested under 'profiles')."""
    import yaml as _yaml  # local import to keep optional

    with open(path, "r", encoding="utf-8") as f:
        data = _yaml.safe_load(f) or {}
    space = data.get("profiles") if isinstance(data.get("profiles"), dict) else data
    if profile not in space:
        raise RuntimeError(f"Profile '{profile}' not found in {path}")
    cfg = space.get(profile) or {}

    def _expand(v):
        if isinstance(v, str):
            return os.path.expandvars(v)
        if isinstance(v, list):
            return [_expand(x) for x in v]
        if isinstance(v, dict):
            return {k: _expand(val) for k, val in v.items()}
        return v

    return _expand(cfg)


def _parse_class_caps(v) -> dict[str, int]:
    if not v:
        return {}
    if isinstance(v, dict):
        try:
            return {str(k): int(v) for k, v in v.items()}
        except Exception:
            pass
    if isinstance(v, str):
        out: dict[str, int] = {}
        for part in v.split(","):
            if not part or "=" not in part:
                continue
            k, s = part.split("=", 1)
            try:
                out[k.strip()] = int(s)
            except Exception:
                pass
        return out
    return {}


def write_decision_log(rows: list[dict]) -> None:
    path = STORE / "decision_log.csv"
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(
            f,
            fieldnames=[
                "ts",
                "tz",
                "interval",
                "adx",
                "ticker",
                "side",
                "price",
                "sl",
                "tp",
                "trail",
            ],
        )
        if new:
            wr.writeheader()
        for r in rows:
            wr.writerow(r)


def read_last_decisions(n: int = 10) -> list[dict[str, str]]:
    path = STORE / "decision_log.csv"
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            rd = list(csv.DictReader(f))
            return rd[-n:]
    except Exception:
        return []


def format_decisions(rows: list[dict[str, str]]) -> str:
    out = ["Recent Decisions:"]
    for r in rows:
        out.append(
            f"{r.get('ts','?')} | {r.get('ticker','?')} {r.get('side','?')} @ {r.get('price','?')} "
            f"(SL {r.get('sl','-')} / TP {r.get('tp','-')} / TR {r.get('trail','-')})"
        )
    return "\n".join(out)


def _params_summary_line(tz: str) -> str:
    p = STORE / "params.json"
    if not p.exists():
        return "WF params last updated: (none)"
    try:
        mtime = dt.datetime.fromtimestamp(p.stat().st_mtime, tz=ZoneInfo(tz))
    except Exception:
        mtime = dt.datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        tz = "UTC"
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        per_ticker = [k for k in obj.keys() if "|" in k and "," not in k]
        group = len(obj) - len(per_ticker)
        return (
            f"WF params last updated: {mtime:%Y-%m-%d %H:%M} {tz} | "
            f"entries: per-ticker={len(per_ticker)}, group={group}"
        )
    except Exception:
        return f"WF params last updated: {mtime:%Y-%m-%d %H:%M} {tz}"


def send_daily_summary(tz: str = "Europe/Dublin") -> str:
    fpath = STORE / "decision_log.csv"
    if not fpath.exists():
        msg = "No decisions logged yet."
        safe_send(msg)
        return msg
    try:
        now_local = dt.datetime.now(ZoneInfo(tz))
    except Exception:
        now_local = dt.datetime.now(timezone.utc)
        tz = "UTC"
    ymd = now_local.strftime("%Y-%m-%d")
    rows: list[dict] = []
    with fpath.open("r", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for r in rd:
            if (r.get("ts") or "").startswith(ymd):
                rows.append(r)
    if not rows:
        msg = f"No decisions today ({ymd} {tz}).\n{_params_summary_line(tz)}"
        safe_send(msg)
        return msg
    by_side = Counter(r["side"] for r in rows)
    by_tkr = Counter(r["ticker"] for r in rows)
    lines = [
        f"Daily Summary {ymd} {tz}",
        f"Total: {len(rows)} | Buys: {by_side.get('Buy',0)} | Sells: {by_side.get('Sell',0)}",
        "Tickers frequency: " + ", ".join(f"{t}:{c}" for t, c in by_tkr.most_common()),
        "Last 5 decisions",
    ]
    for r in rows[-5:]:
        lines.append(
            f"{r['ts']} | {r['ticker']} {r['side']} @ {r['price']} "
            f"(SL {r.get('sl')} / TP {r.get('tp')} / TR {r.get('trail')})"
        )
    lines.append(_params_summary_line(tz))
    msg = "\n".join(lines)
    safe_send(msg)
    return msg


def vote_signals(maps: dict[str, dict], weights: dict[str, float] | None = None) -> dict:
    weights = weights or {}
    out: dict = {}
    if not maps:
        return out
    keys = set().union(*[m.keys() for m in maps.values()])
    for k in keys:
        tally: dict[str, float] = {}
        for iv, m in maps.items():
            side = m.get(k, "Hold")
            w = weights.get(iv, 1.0)
            tally[side] = tally.get(side, 0.0) + w
        out[k] = max(tally, key=tally.get)
    return out


def _load_default_config() -> dict:
    path = ROOT / "config.yaml"
    if yaml is None or not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def run_cycle(
    watch,
    size,
    grace,
    risk,
    qty,
    force=False,
    interval="1d",
    adx=20,
    tz="Europe/Dublin",
    ema_fast=20,
    ema_slow=50,
    macd_signal=9,
    ml_model: "PriceDirectionModel | None" = None,
    ml_threshold: float = 0.6,
    ml_blend: str = "auto",
    max_trades=999,
    intervals="",
    interval_weights=None,
    vote=False,
    use_params=False,
    max_portfolio_risk=0.02,
    budget_mode: str = "auto",
    cooldown_min=30,
    cap_crypto=2,
    cap_equity=2,
    cap_per_ticker=1,
    risk_budget_crypto=0.01,
    risk_budget_equity=0.01,
    class_caps=None,
    class_risk_budget=None,
    sl_atr=2.0,
    tp_atr=4.0,
    trail_atr=0.0,
    max_trade_risk: float = 0.01,
    broker: "Broker | None" = None,
    dry_run: bool = False,
    retrain_on_dry_run: bool = True,
    retrain_interval_hours: int = 4,
):
    equity = qty
    # Implementation continues... (truncated in this chunk)
    if broker is not None and hasattr(broker, "get_equity"):
        try:
            val = broker.get_equity()
            if val is not None:
                equity = float(val)
        except Exception as e:
            log.error("Broker equity fetch failed: %s", e)

    if not watch:
        log.info("Watchlist empty – skipping cycle.")
        return

    # Market hours gate: if equity market closed, still allow crypto-only flow
    if not force and not market_open():
        if any(is_crypto(t) for t in watch):
            watch = [t for t in watch if is_crypto(t)]
            log.info("Market closed – proceeding with crypto-only subset: %s", ",".join(watch))
        else:
            log.info("Market closed – skipping cycle.")
            return
    try:
        now_local = dt.datetime.now(ZoneInfo(tz))
        tz_label = tz
    except Exception:
        now_local = dt.datetime.now(timezone.utc)
        tz_label = "UTC"
    end = dt.date.today().isoformat()
    lookback_days = _max_lookback_days(interval)
    start = (dt.date.today() - dt.timedelta(days=lookback_days)).isoformat()

    # Ensure tickers is always defined before we call get_price_data or reference it in except
    tickers = []  # default so except block can reference it safely

    # choose tickers earlier in the function (example)
    market_closed = not market_open()
    if market_closed:
        tickers = ["BTC-USD","ETH-USD","SOL-USD","ADA-USD","LTC-USD","BCH-USD"]
    else:
        tickers = watch  # ...existing code that sets full universe...

    # Replace the call to get_price_data(...) with this block:
    try:
        price = get_price_data(tickers, start, end, interval=interval)
    except HTTPError as e:
        msg = str(e)
        if "401" in msg or "Unauthorized" in msg or "unauthorized" in msg.lower():
            log.error("Alpaca unauthorized (401): %s -- trying Yahoo fallback", e)
            try:
                price = _fetch_via_yahoo(tickers, start, end, interval)
                log.info("Fetched crypto data via Yahoo for tickers: %s", tickers)
            except Exception as e2:
                log.error("Yahoo fallback failed: %s", e2)
                raise
        else:
            log.error("Data download failed: %s", e)
            raise
    except Exception as e:
        # non-HTTP errors -> try yahoo as a secondary attempt
        try:
            price = _fetch_via_yahoo(tickers, start, end, interval)
            log.info("Fetched crypto data via Yahoo for tickers: %s", tickers)
        except Exception as e2:
            log.error("Data download failed and Yahoo fallback failed: %s / %s", e, e2)
            raise

    base_sig = generate_signals(
        price,
        adx_threshold=adx,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
    )
    log.info("Signals: %s", base_sig)

    # Multi-interval voting (accept list OR string)
    if vote and intervals:
        weights = _parse_interval_weights(interval_weights)
        maps = {
            interval: {t: (d["action"] if isinstance(d, dict) else d) for t, d in base_sig.items()}
        }
        for itv in _normalize_intervals(intervals):
            if itv in maps:
                continue
            try:
                lb_v = _max_lookback_days(itv)
                start_v = (dt.date.today() - dt.timedelta(days=lb_v)).isoformat()
                price_v = get_price_data(tickers, start_v, end, interval=itv)
                sig_v = generate_signals(price_v, adx_threshold=adx, ema_fast=ema_fast, ema_slow=ema_slow)
                maps[itv] = {t: (d["action"] if isinstance(d, dict) else d) for t, d in sig_v.items()}
            except Exception as e:
                log.error("Voting interval %s failed: %s", itv, e)
        voted = vote_signals(maps, weights)
        base_sig = {t: {"action": s, "confidence": 1.0} for t, s in voted.items()}

    params = load_params() if use_params else {}
    key_group = ",".join(sorted(watch)) + "|" + interval
    defaults = {
        "adx": adx,
        "sl_atr": sl_atr,
        "tp_atr": tp_atr,
        "trail_atr": trail_atr,
        "ema_fast": ema_fast,
        "ema_slow": ema_slow,
        "macd_signal": macd_signal,
    }

    header = f"PRE-TRADE {now_local:%Y-%m-%d %H:%M} {tz_label} (int={interval})"
    lines = [header]
    rows = []
    last_state = _load_last_signals()
    now_iso = now_local.isoformat(timespec="minutes")

    per_cls: Counter = Counter()
    per_tkr: dict[str, int] = {}
    candidates: list[tuple[str, str, str, dict]] = []

    caps = _parse_class_caps(class_caps)
    caps.setdefault("crypto", cap_crypto)
    caps.setdefault("equity", cap_equity)
    default_cap = caps.get("_", max_trades)

    limits_hit: set[str] = set()

    # ----- ML helpers -----
    def _ml_choose_mode_auto(equity_val: float, conf: float) -> str:
        try:
            if equity_val >= 25000 and conf >= max(0.55, ml_threshold + 0.05):
                return "vote"
        except Exception:
            pass
        return "filter"

    def _apply_ml_blend(ticker: str, side_in: str, sig_conf_in: float) -> tuple[str, float]:
        side_out, conf_out = side_in, sig_conf_in
        if ml_model is None or ml_blend == "off":
            return side_out, conf_out
        try:
            close = price[ticker]["Close"].dropna()
            ml_side, ml_conf = ml_model.predict_signal(close)
        except Exception:
            return side_out, conf_out
        mode = ml_blend
        if mode == "auto":
            mode = _ml_choose_mode_auto(equity, ml_conf)
        if mode == "filter":
            if ml_conf >= ml_threshold and ml_side == side_out:
                return side_out, min(1.0, max(conf_out, ml_conf))
            return "Hold", 0.0
        if mode == "override":
            if ml_conf >= ml_threshold:
                return ml_side, ml_conf
            return side_out, conf_out
        if mode == "vote":
            if ml_conf < ml_threshold:
                return side_out, conf_out
            if ml_side == side_out:
                return side_out, min(1.0, (conf_out + ml_conf) / 2.0)
            return (ml_side, ml_conf) if ml_conf >= conf_out else (side_out, conf_out)
        return side_out, conf_out

    # Filter candidates by caps and tuned ADX
    for tkr in tickers:
        sig = base_sig.get(tkr, "Hold")
        side = sig.get("action", "Hold") if isinstance(sig, dict) else sig
        sig_conf = float(sig.get("confidence", 0.0)) if isinstance(sig, dict) else 0.0
        if side == "Hold":
            continue
        tkr = tkr.replace(" ", "").replace("\u00A0", "")
        cls = classify(tkr)

        tuned = tuned_for(tkr, interval, key_group, params, defaults)
        tuned_adx = int(tuned.get("adx", adx))
        # If tuned EMAs exist, recompute this ticker's signal with tuned params
        try:
            tf = int(tuned.get("ema_fast", ema_fast))
            ts = int(tuned.get("ema_slow", ema_slow))
            if tf != ema_fast or ts != ema_slow or tuned_adx != adx:
                one_price = price[[tkr]]
                sig_map = generate_signals(
                    one_price,
                    adx_threshold=tuned_adx,
                    ema_fast=tf,
                    ema_slow=ts,
                )
                if tkr in sig_map:
                    recomputed = sig_map[tkr]
                    side = recomputed.get("action", side) if isinstance(recomputed, dict) else str(recomputed)
                    sig_conf = float(recomputed.get("confidence", sig_conf)) if isinstance(recomputed, dict) else sig_conf
        except Exception:
            pass
        try:
            series_adx = _adx(price[tkr]["High"], price[tkr]["Low"], price[tkr]["Close"]).dropna()
            if len(series_adx) and series_adx.iloc[-1] < tuned_adx:
                continue
        except Exception:
            pass

        # Apply ML blending if enabled
        side, sig_conf = _apply_ml_blend(tkr, side, sig_conf)
        if side == "Hold":
            continue

        if per_cls[cls] >= caps.get(cls, default_cap):
            log.info("Cap skip (%s): %s", cls, tkr)
            limits_hit.add("max positions")
            continue
        if per_tkr.get(tkr, 0) >= cap_per_ticker:
            log.info("Cap skip (per-ticker): %s", tkr)
            continue

        candidates.append((tkr, side, cls, tuned))
        per_cls[cls] += 1
        per_tkr[tkr] = per_tkr.get(tkr, 0) + 1
        if len(candidates) >= max_trades:
            break

    # Risk budgeting per class
    planned_counts = Counter(cls for _, _, cls, _ in candidates)
    classes = list(planned_counts.keys())
    budgets_input = _parse_interval_weights(class_risk_budget)
    if not budgets_input and (risk_budget_crypto > 0 or risk_budget_equity > 0):
        budgets_input = {"crypto": risk_budget_crypto, "equity": risk_budget_equity}

    # Optional: auto allocate budgets by confidence and inverse ATR
    auto_budget: dict[str, float] | None = None
    if not budgets_input and budget_mode == "auto" and classes:
        cls_scores: dict[str, float] = {c: 0.0 for c in classes}
        for (tkr, _side, cls, _tuned) in candidates:
            try:
                last = float(price[tkr]["Close"].dropna().iloc[-1])
                high = price[tkr]["High"].dropna().tail(15)
                low = price[tkr]["Low"].dropna().tail(15)
                cls_px = price[tkr]["Close"].dropna().tail(15)
                atr_val = float(_atr(high, low, cls_px).iloc[-1]) if len(cls_px) >= 2 else max(1.0, last * 0.01)
                atr_pct = atr_val / max(1e-9, last)
                conf = 0.5
                try:
                    bs = base_sig.get(tkr)
                    if isinstance(bs, dict):
                        conf = float(bs.get("confidence", 0.5))
                except Exception:
                    pass
                weight = conf / max(atr_pct, 1e-6)
                cls_scores[cls] = cls_scores.get(cls, 0.0) + max(weight, 0.0)
            except Exception:
                cls_scores[cls] = cls_scores.get(cls, 0.0) + 0.0
        total = sum(cls_scores.values()) or 1.0
        auto_budget = {c: max_portfolio_risk * (cls_scores[c] / total) for c in classes}

    if budgets_input:
        specified_total = sum(budgets_input.get(cls, 0.0) for cls in classes)
        unspecified = [c for c in classes if c not in budgets_input]
        remaining_port = max(0.0, max_portfolio_risk - specified_total)
        budget = {cls: budgets_input.get(cls, 0.0) for cls in classes}
        if unspecified:
            per_cls_budget = remaining_port / len(unspecified)
            for c in unspecified:
                budget[c] = per_cls_budget
    elif auto_budget is not None:
        budget = auto_budget
    else:
        per_cls_budget = max_portfolio_risk / max(1, len(classes))
        budget = {cls: per_cls_budget for cls in classes}

    remaining = planned_counts.copy()
    remaining_budget = budget.copy()

    # Build lines + decision log
    for (tkr, side, cls, tuned) in candidates:
        key = f"{tkr}:{side}:{interval}"
        last_ts = last_state.get(key)
        if last_ts:
            try:
                prev = dt.datetime.fromisoformat(last_ts)
                delta_min = (now_local - prev).total_seconds() / 60.0
                if delta_min < cooldown_min:
                    log.info("Cooldown skip: %s (last %.1f min ago)", key, delta_min)
                    remaining[cls] -= 1
                    continue
            except Exception:
                pass

        last = float(price[tkr]["Close"].iloc[-1])

        high = price[tkr]["High"].dropna().tail(15)
        low = price[tkr]["Low"].dropna().tail(15)
        cls_px = price[tkr]["Close"].dropna().tail(15)
        atr_val = float(_atr(high, low, cls_px).iloc[-1]) if len(cls_px) >= 2 else max(1.0, last * 0.01)

        sl_mult = float(tuned.get("sl_atr", tuned.get("sl", defaults["sl_atr"])))
        tp_mult = float(tuned.get("tp_atr", tuned.get("tp", defaults["tp_atr"])))
        tr_mult = float(tuned.get("trail_atr", defaults["trail_atr"]))

        sl = None
        if sl_mult > 0:
            sl = round(last - sl_mult * atr_val, 2) if side == "Buy" else round(last + sl_mult * atr_val, 2)
        tp = None
        if tp_mult > 0:
            tp = round(last + tp_mult * atr_val, 2) if side == "Buy" else round(last - tp_mult * atr_val, 2)
        trail_start = None
        if tr_mult > 0:
            trail_start = round(last - tr_mult * atr_val, 2) if side == "Buy" else round(last + tr_mult * atr_val, 2)

        planned_left = max(1, remaining[cls])
        per_trade_budget = max(0.0, remaining_budget[cls]) / planned_left
        per_trade_risk = min(
            per_trade_budget,
            risk,
            max_trade_risk,
        )

        if per_trade_budget <= 0:
            limits_hit.add("risk")
        trade_qty = qty_from_atr(atr_val, equity, per_trade_risk)

        if broker is not None:
            try:
                result = broker.submit_order(
                    tkr, side, trade_qty, entry=last, sl=sl, tp=tp, tif="day", dry_run=dry_run
                )
            except Exception as e:
                log.error("Broker submit failed for %s: %s", tkr, e)
            else:
                try:
                    order_id = None
                    if isinstance(result, dict):
                        order_id = result.get("id") or result.get("order_id")
                    broker_name = (
                        getattr(broker, "__class__", type(broker)).__name__.replace("Broker", "").lower()
                    )
                    log_trade(
                        {
                            "time": now_iso,
                            "ticker": tkr,
                            "side": side.lower(),
                            "entry": last,
                            "sl": sl,
                            "tp": tp,
                            "exit": None,
                            "exit_reason": None,
                            "atr": atr_val,
                            "r_multiple": None,
                            "fees": 0.0,
                            "broker": broker_name,
                            "order_id": order_id or f"AUTO-{tkr}-{now_local:%Y%m%d%H%M}",
                        }
                    )
                except Exception as e:
                    log.error("Trade log write failed for %s: %s", tkr, e)

        risk_abs = round(per_trade_risk * equity, 2)
        atr_pct = (atr_val / last) * 100.0 if last else 0.0
        if sl is not None and tp is not None:
            if side == "Buy":
                r_multiple = (tp - last) / max(1e-9, (last - sl))
            else:
                r_multiple = (last - tp) / max(1e-9, (sl - last))
        else:
            r_multiple = 0.0

        line = (
            f"{tkr}  {side} | Px {last:.2f} | SL {sl if sl is not None else '-'} | TP {tp if tp is not None else '-'}"
        )
        if trail_start is not None:
            line += f" | TR {trail_start:.2f}"
        line += f" | Qty {trade_qty} | ATR {atr_pct:.2f}% | R {r_multiple:.2f} | Risk {risk_abs}"

        lines.append(line)
        rows.append(
            {
                "ts": now_iso,
                "tz": tz_label,
                "interval": interval,
                "adx": int(tuned.get("adx", adx)),
                "ticker": tkr,
                "side": side,
                "price": round(last, 2),
                "sl": sl,
                "tp": tp,
                "trail": trail_start,
            }
        )

        remaining_budget[cls] -= per_trade_risk
        remaining[cls] -= 1
        last_state[key] = now_iso

    if len(lines) == 1:
        caps_msg = ", ".join(f"{k}={v}" for k, v in caps.items()) or "none"
        lines.append(
            f"All alerts suppressed by caps/cooldown/filters (caps: {caps_msg}, per_ticker={cap_per_ticker}; cooldown={cooldown_min} min)."
        )

    txt = "\n".join(lines)
    safe_send(txt)
    for _ln in lines:
        log.info(_ln)

    if rows:
        write_decision_log(rows)
    _save_last_signals(last_state)

    # Grace delay
    time.sleep(max(0, grace))

    # Backtest preview on the same data slice
    sig_map = {k: (v["action"] if isinstance(v, dict) else v) for k, v in base_sig.items()}
    pnl, stats, _ = backtest(
        price,
        sig_map,
        max_hold=5,
        cost=0.0002,
        sl_atr=defaults["sl_atr"],
        tp_atr=defaults["tp_atr"],
        trail_atr=defaults["trail_atr"],
        risk_pct=risk,
        equity=equity,
    )

    last_cum = pnl["cum_return"].iloc[-1]
    msg = (
        "Backtest cum return (1yr): "
        f"{last_cum:.2f}x | Sharpe {stats['sharpe']:.2f} | "
        f"Max DD {stats['max_drawdown']:.2%} | Win rate {stats['win_rate']:.2%}"
    )
    safe_send(msg)

    summary = f"Summary: signals={len(base_sig)}, orders={len(rows)}"
    if limits_hit:
        summary += " | limits: " + ",".join(sorted(limits_hit))
    safe_send(summary)
    log.info(summary)

    # Persist strategy state for digest/reporting
    try:
        state = {
            "ts": now_iso,
            "interval": interval,
            "defaults": defaults,
            "use_params": bool(use_params),
            "ml": {"enabled": ml_model is not None, "threshold": ml_threshold, "blend": ml_blend},
            "risk": {"per_trade": risk, "max_portfolio": max_portfolio_risk, "budget_mode": budget_mode},
            "class_budgets": budget,
            "caps": {"class_caps": caps, "cap_per_ticker": cap_per_ticker},
            "broker": getattr(broker, "__class__", type(broker)).__name__.replace("Broker", "").lower() if broker else "manual",
            "dry_run": bool(dry_run),
        }
        (STORE / "strategy_state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception:
        pass

    allowed = (not dry_run) or bool(retrain_on_dry_run)
    if allowed:
        try:
            from SmartCFDTradingAgent.walk_forward import retrain_from_trade_log
            retrain_from_trade_log(min_hours_between=int(retrain_interval_hours))
        except Exception as e:  # pragma: no cover - best effort
            log.error("Retraining failed: %s", e)
    return pnl, stats, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", nargs="+", help="Symbols (Yahoo): e.g., SPY QQQ or BTC-USD ETH-USD")
    ap.add_argument("--size", type=int, default=5)
    ap.add_argument("--grace", type=int, default=900)
    default_risk = float(os.getenv("RISK_PCT", "0.01"))
    ap.add_argument("--risk", type=float, default=default_risk)
    ap.add_argument(
        "--max-trade-risk",
        type=float,
        default=default_risk,
        help="Maximum fraction of equity risked per trade",
    )
    ap.add_argument("--equity", type=float, default=1000.0)
    ap.add_argument("--sl-atr", type=float, default=2.0, help="Stop loss ATR multiple (0 disables)")
    ap.add_argument("--tp-atr", type=float, default=4.0, help="Take profit ATR multiple (0 disables)")
    ap.add_argument("--trail-atr", type=float, default=0.0, help="Trailing stop ATR multiple (0 disables)")
    ap.add_argument("--qty", type=float, default=1000.0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--interval", default="1d")
    ap.add_argument("--adx", type=int, default=20)
    ap.add_argument("--ema-fast", type=int, default=20)
    ap.add_argument("--ema-slow", type=int, default=50)
    ap.add_argument("--macd-signal", type=int, default=9)
    ap.add_argument("--tz", default="Europe/Dublin")
    ap.add_argument("--ml-model", help="Path to trained ML model for signal blending")
    ap.add_argument(
        "--ml-threshold", type=float, default=0.6, help="Probability threshold for ML blending/override"
    )
    ap.add_argument(
        "--ml-blend",
        choices=["off", "filter", "override", "vote", "auto"],
        default=os.getenv("ML_BLEND", "auto"),
    )
    ap.add_argument("--broker", choices=["manual", "alpaca"], default="manual")
    ap.add_argument("--dry-run", action="store_true")
    # Caps & budgets
    ap.add_argument("--max-trades", type=int, default=999)
    ap.add_argument("--cap-crypto", type=int, default=2)
    ap.add_argument("--cap-equity", type=int, default=2)
    ap.add_argument("--cap-per-ticker", type=int, default=1)
    ap.add_argument("--cooldown-min", type=int, default=30)
    ap.add_argument("--max-portfolio-risk", type=float, default=0.02)
    ap.add_argument("--risk-budget-crypto", type=float, default=0.01)
    ap.add_argument("--risk-budget-equity", type=float, default=0.01)
    ap.add_argument("--class-caps", default="", help="Per-class caps, e.g. crypto=2,forex=1")
    ap.add_argument("--class-risk-budget", default="", help="Per-class risk budgets, e.g. crypto=0.01,forex=0.005")
    ap.add_argument("--budget-mode", choices=["equal", "auto"], default=os.getenv("BUDGET_MODE", "auto"))
    # Voting / params
    ap.add_argument("--intervals", default="")
    ap.add_argument("--interval-weights", default="", help="Weights for voting intervals, e.g. 15m=1,1h=2")
    ap.add_argument("--vote", action="store_true")
    ap.add_argument("--use-params", action="store_true")
    ap.add_argument("--retrain-on-dry-run", action="store_true", default=True)
    ap.add_argument(
        "--retrain-interval-hours", type=int, default=int(os.getenv("RETRAIN_INTERVAL_HOURS", "4"))
    )
    # Utility / reporting
    ap.add_argument("--show-decisions", type=int, default=0)
    ap.add_argument("--to-telegram", action="store_true")
    ap.add_argument("--daily-summary", action="store_true")
    # New: config profiles
    ap.add_argument("--config", help="Path to .yml/.yaml or .json config file")
    ap.add_argument("--profile", help="Profile name inside the config (e.g., crypto_1h)")

    defaults = {a.dest: a.default for a in ap._actions if a.dest != "help"}
    cfg_defaults = {k: v for k, v in _load_default_config().items() if k in defaults}
    if cfg_defaults:
        ap.set_defaults(**cfg_defaults)
    env_defaults: dict[str, object] = {}
    for k, v in defaults.items():
        env_val = os.getenv(k.upper())
        if env_val is None:
            continue
        try:
            if isinstance(v, bool):
                env_defaults[k] = str(env_val).lower() in {"1", "true", "yes", "on"}
            elif isinstance(v, list):
                env_defaults[k] = str(env_val).split()
            else:
                env_defaults[k] = type(v)(env_val)
        except Exception:
            env_defaults[k] = env_val
    if env_defaults:
        ap.set_defaults(**env_defaults)

    args = ap.parse_args()
    from SmartCFDTradingAgent.brokers import get_broker
    broker = get_broker(args.broker) if args.broker else None

    if args.show_decisions > 0:
        rows = read_last_decisions(args.show_decisions)
        msg = format_decisions(rows)
        log.info(msg)
        if args.to_telegram:
            safe_send(msg)
        return
    if args.daily_summary:
        send_daily_summary(args.tz)
        return

    # If a config file is provided, load it and run with that profile (CLI still allows --force)
    if args.config:
        cfg = load_profile_config(args.config, args.profile)
        watch = cfg.get("watch", [])
        if isinstance(watch, str):
            watch = watch.split()
        if not watch:
            log.error("Config missing 'watch' list.")
            sys.exit(2)
        model_cfg = None
        ml_path = cfg.get("ml_model", args.ml_model)
        if ml_path:
            # expand environment vars and resolve relative paths
            ml_path_resolved = Path(os.path.expandvars(str(ml_path)))
            if not ml_path_resolved.exists():
                log.error(
                    "ML model path from config does not exist: %s (resolved: %s)",
                    ml_path,
                    ml_path_resolved,
                )
            else:
                model_cfg = None
                try:
                    from SmartCFDTradingAgent.ml_models import PriceDirectionModel
                    model_cfg = PriceDirectionModel.load(str(ml_path_resolved))
                except Exception as e_load:
                    log.warning("PriceDirectionModel.load failed: %s. Trying json/pickle fallback.", e_load)
                    try:
                        # try JSON first (human-editable). If file is binary pickle, this will raise.
                        raw = json.loads(ml_path_resolved.read_text(encoding="utf-8"))
                        model_cfg = _DummyModel(raw)
                    except Exception:
                        # last resort: try pickle -> if it's a simple dict we can wrap it
                        try:
                            import pickle
                            with ml_path_resolved.open("rb") as fh:
                                raw = pickle.load(fh)
                            if isinstance(raw, dict):
                                model_cfg = _DummyModel(raw)
                            else:
                                # not a dict/object we understand -> ignore and warn
                                log.error("ML model file present but not loadable as known format.")
                        except Exception as e_pickle:
                            log.error("Fallback ML load failed: %s", e_pickle)
        run_cycle(
            watch=watch,
            size=int(cfg.get("size", args.size)),
            grace=int(cfg.get("grace", args.grace)),
            qty=float(cfg.get("qty", args.qty)),
            risk=float(cfg.get("risk", args.risk)),
            force=(args.force or bool(cfg.get("force", False))),
            interval=cfg.get("interval", args.interval),
            adx=int(cfg.get("adx", args.adx)),
            tz=cfg.get("tz", args.tz),
            ema_fast=int(cfg.get("ema_fast", args.ema_fast)),
            ema_slow=int(cfg.get("ema_slow", args.ema_slow)),
            macd_signal=int(cfg.get("macd_signal", args.macd_signal)),
            ml_model=model_cfg,
            ml_threshold=float(cfg.get("ml_threshold", args.ml_threshold)),
            ml_blend=str(cfg.get("ml_blend", args.ml_blend)),
            max_trades=int(cfg.get("max_trades", args.max_trades)),
            intervals=cfg.get("intervals", args.intervals),
            interval_weights=cfg.get("interval_weights", args.interval_weights),
            vote=bool(cfg.get("vote", args.vote)),
            use_params=bool(cfg.get("use_params", args.use_params)),
            max_portfolio_risk=float(cfg.get("max_portfolio_risk", args.max_portfolio_risk)),
            budget_mode=str(cfg.get("budget_mode", args.budget_mode)),
            cooldown_min=int(cfg.get("cooldown_min", args.cooldown_min)),
            cap_crypto=int(cfg.get("cap_crypto", args.cap_crypto)),
            cap_equity=int(cfg.get("cap_equity", args.cap_equity)),
            cap_per_ticker=int(cfg.get("cap_per_ticker", args.cap_per_ticker)),
            risk_budget_crypto=float(cfg.get("risk_budget_crypto", args.risk_budget_crypto)),
            risk_budget_equity=float(cfg.get("risk_budget_equity", args.risk_budget_equity)),
            class_caps=_parse_class_caps(cfg.get("class_caps", args.class_caps)),
            class_risk_budget=_parse_interval_weights(cfg.get("class_risk_budget", args.class_risk_budget)),
            sl_atr=float(cfg.get("sl_atr", args.sl_atr)),
            tp_atr=float(cfg.get("tp_atr", args.tp_atr)),
            trail_atr=float(cfg.get("trail_atr", args.trail_atr)),
            broker=broker,
            dry_run=args.dry_run,
            retrain_on_dry_run=bool(cfg.get("retrain_on_dry_run", args.retrain_on_dry_run)),
            retrain_interval_hours=int(cfg.get("retrain_interval_hours", args.retrain_interval_hours)),
        )
        return

    if not args.watch:
        log.error("Error: --watch is required for normal run.")
        sys.exit(2)

    model = None
    if args.ml_model:
        ml_path_resolved = Path(os.path.expandvars(str(args.ml_model)))
        if not ml_path_resolved.exists():
            log.error("ML model path does not exist: %s (resolved: %s)", args.ml_model, ml_path_resolved)
        else:
            try:
                from SmartCFDTradingAgent.ml_models import PriceDirectionModel

                model = PriceDirectionModel.load(str(ml_path_resolved))
            except Exception as e:
                log.error("Failed to load ML model: %s", e)

    try:
        run_cycle(
            watch=args.watch,
            size=args.size,
            grace=args.grace,
            qty=args.qty,
            risk=args.risk,
            max_trade_risk=args.max_trade_risk,
            force=args.force,
            interval=args.interval,
            adx=args.adx,
            tz=args.tz,
            ema_fast=args.ema_fast,
            ema_slow=args.ema_slow,
            macd_signal=args.macd_signal,
            ml_model=model,
            ml_threshold=args.ml_threshold,
            ml_blend=args.ml_blend,
            max_trades=args.max_trades,
            intervals=args.intervals,
            interval_weights=args.interval_weights,
            vote=args.vote,
            use_params=args.use_params,
            max_portfolio_risk=args.max_portfolio_risk,
            budget_mode=args.budget_mode,
            cooldown_min=args.cooldown_min,
            cap_crypto=args.cap_crypto,
            cap_equity=args.cap_equity,
            cap_per_ticker=args.cap_per_ticker,
            risk_budget_crypto=args.risk_budget_crypto,
            risk_budget_equity=args.risk_budget_equity,
            class_caps=_parse_class_caps(args.class_caps),
            class_risk_budget=_parse_interval_weights(args.class_risk_budget),
            sl_atr=args.sl_atr,
            tp_atr=args.tp_atr,
            trail_atr=args.trail_atr,
            broker=broker,
            dry_run=args.dry_run,
            retrain_on_dry_run=args.retrain_on_dry_run,
            retrain_interval_hours=args.retrain_interval_hours,
        )
    except Exception as e:
        log.exception("Pipeline crashed: %s", e)
        safe_send(f"⚠️ SmartCFD crashed\n{e}")

def _fetch_via_yahoo(tickers, start, end, interval):
    iv_map = {"1h":"60m","60m":"60m","1d":"1d","1m":"1m","5m":"5m","15m":"15m","30m":"30m"}
    yf_iv = iv_map.get(interval, interval)
    df = yf.download(tickers, start=start, end=end, interval=yf_iv, group_by="ticker", threads=True, progress=False)
    out = {}
    if len(tickers) == 1:
        out[tickers[0]] = df[["Open","High","Low","Close","Volume"]].copy()
    else:
        for t in tickers:
            if t in df.columns:
                sub = df[t].copy()
            else:
                # when yfinance returns flat, try selecting by suffix
                sub = df[[c for c in df.columns if c[1:].endswith(("Open","High","Low","Close","Volume"))]] if hasattr(df.columns, 'levels') else pd.DataFrame()
            if not sub.empty:
                out[t] = sub[["Open","High","Low","Close","Volume"]].copy()
    if not out:
        raise RuntimeError("Yahoo returned no usable data")
    return out

if __name__ == "__main__":
    load_dotenv()
    main()
