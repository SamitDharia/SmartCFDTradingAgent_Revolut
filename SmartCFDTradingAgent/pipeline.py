from __future__ import annotations

# Must be first: force yfinance to use safe downloader (no SSL issues)
import SmartCFDTradingAgent.utils.no_ssl  # noqa: F401

import os
os.environ.setdefault("CURL_CA_BUNDLE", "")
os.environ.setdefault("YF_DISABLE_CURL", "1")

import argparse, time, datetime as dt, csv, sys, json
from dotenv import load_dotenv

load_dotenv()

from datetime import timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from collections import Counter

from SmartCFDTradingAgent.utils.logger import get_logger
from SmartCFDTradingAgent.utils.market_time import market_open
from SmartCFDTradingAgent.utils.telegram import send as tg_send
from SmartCFDTradingAgent.rank_assets import top_n
from SmartCFDTradingAgent.data_loader import get_price_data
from SmartCFDTradingAgent.signals import generate_signals
from SmartCFDTradingAgent.backtester import backtest
from SmartCFDTradingAgent.position import qty_from_atr
from SmartCFDTradingAgent.indicators import adx as _adx
try:  # PyYAML may be missing in minimal environments
    import yaml  # type: ignore
except Exception:  # pragma: no cover - fallback for tests
    yaml = None  # type: ignore

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - hint only
    from SmartCFDTradingAgent.ml_models import PriceDirectionModel

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - hint only
    from SmartCFDTradingAgent.ml_models import PriceDirectionModel

log = get_logger()
ROOT = Path(__file__).resolve().parent
STORE = ROOT / "storage"
STORE.mkdir(exist_ok=True)

# ----------------- helpers -----------------
def safe_send(msg: str) -> None:
    try:
        tg_send(msg)
    except Exception as e:
        log.error("Telegram send failed: %s", e)

# --- asset classification ---
ASSET_MAP: dict[str, str] = {}


def _load_asset_classes(path: Path | None = None) -> dict[str, str]:
    """Load ticker -> class mapping from a YAML file.

    The YAML may map classes to lists of tickers or tickers to classes.
    Any tickers not present default to ``equity``.
    """
    if yaml is None:
        return {}
    path = path or ROOT / "assets.yml"
    try:
        data = yaml.safe_load(path.read_text()) or {}
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
    """Accept list/tuple/set or comma-separated string; return clean list of strings."""
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
    # anything else -> single item
    s = str(intervals).strip()
    return [s] if s else []

def _parse_interval_weights(weights) -> dict[str, float]:
    """Parse interval weight mapping from a string or dict.

    Accepts strings like "15m=1,1h=2" or a dict mapping interval to weight.
    Returns a dict with float weights, defaulting to empty dict if parsing fails.
    """
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
            part = part.strip()
            if not part or "=" not in part:
                continue
            iv, w = part.split("=", 1)
            try:
                out[iv.strip()] = float(w)
            except ValueError:
                continue
        return out
    if isinstance(weights, (list, tuple)):
        return _parse_interval_weights(",".join(map(str, weights)))
    return {}


def _parse_class_caps(caps) -> dict[str, int]:
    """Parse class cap mapping from a string or dict."""
    if not caps:
        return {}
    if isinstance(caps, dict):
        out: dict[str, int] = {}
        for k, v in caps.items():
            try:
                out[str(k).strip()] = int(v)
            except (TypeError, ValueError):
                continue
        return out
    if isinstance(caps, str):
        out: dict[str, int] = {}
        for part in caps.split(","):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            try:
                out[k.strip()] = int(v)
            except ValueError:
                continue
        return out
    if isinstance(caps, (list, tuple)):
        return _parse_class_caps(",".join(map(str, caps)))
    return {}
# -------------------------------------------

def write_decision_log(rows: list[dict]):
    fpath = STORE / "decision_log.csv"
    new_file = not fpath.exists()
    fieldnames = ["ts","tz","interval","adx","ticker","side","price","sl","tp"]
    with fpath.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if new_file:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fieldnames})

def read_last_decisions(n: int) -> list[dict]:
    fpath = STORE / "decision_log.csv"
    if not fpath.exists():
        return []
    with fpath.open("r", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        rows = list(rd)
    return rows[-n:] if n > 0 else rows

def format_decisions(rows: list[dict]) -> str:
    if not rows:
        return "No decisions logged yet."
    lines = ["Last Decisions:"]
    for r in rows:
        lines.append(f"{r['ts']} {r['tz']} | {r['ticker']} {r['side']} | Px {r['price']} | SL {r['sl']} | TP {r['tp']} (int={r['interval']}, ADX>={r['adx']})")
    return "\n".join(lines)

def _params_summary_line(tz: str) -> str:
    p = STORE / "params.json"
    if not p.exists():
        return "WF params last updated: (none)"
    try:
        # last write time in requested tz
        mtime = dt.datetime.fromtimestamp(p.stat().st_mtime, tz=ZoneInfo(tz))
    except Exception:
        mtime = dt.datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc); tz = "UTC"
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        per_ticker = [k for k in obj.keys() if "|" in k and "," not in k]
        group = len(obj) - len(per_ticker)
        return f"WF params last updated: {mtime:%Y-%m-%d %H:%M} {tz} | entries: per-ticker={len(per_ticker)}, group={group}"
    except Exception:
        return f"WF params last updated: {mtime:%Y-%m-%d %H:%M} {tz}"

def send_daily_summary(tz: str = "Europe/Dublin") -> str:
    fpath = STORE / "decision_log.csv"
    if not fpath.exists():
        msg = "No decisions logged yet."
        safe_send(msg); return msg
    try:
        now_local = dt.datetime.now(ZoneInfo(tz))
    except Exception:
        now_local = dt.datetime.now(timezone.utc); tz = "UTC"
    ymd = now_local.strftime("%Y-%m-%d")
    rows = []
    with fpath.open("r", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for r in rd:
            if (r.get("ts") or "").startswith(ymd):
                rows.append(r)
    if not rows:
        msg = f"No decisions today ({ymd} {tz}).\n{_params_summary_line(tz)}"
        safe_send(msg); return msg
    by_side = Counter(r["side"] for r in rows)
    by_tkr  = Counter(r["ticker"] for r in rows)
    lines = [
        f"Daily Summary {ymd} {tz}",
        f"Total: {len(rows)} | Buys: {by_side.get('Buy',0)} | Sells: {by_side.get('Sell',0)}",
        "Tickers frequency: " + ", ".join(f"{t}:{c}" for t,c in by_tkr.most_common()),
        "— Last 5 decisions —",
    ]
    for r in rows[-5:]:
        lines.append(f"{r['ts']} | {r['ticker']} {r['side']} @ {r['price']} (SL {r['sl']} / TP {r['tp']})")
    lines.append(_params_summary_line(tz))
    msg = "\n".join(lines)
    safe_send(msg)
    return msg

def vote_signals(maps: dict[str, dict], weights: dict[str, float] | None = None) -> dict:
    """Weighted majority vote across interval signal maps.

    ``maps`` should map interval strings to signal dictionaries. ``weights``
    assigns a numeric weight to each interval; unspecified intervals default to 1.
    """
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

def _max_lookback_days(iv: str) -> int:
    iv = (iv or "").lower()
    intraday = {"1m","2m","5m","15m","30m","60m","90m","1h"}
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
# -----------------------------

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

# -------- Config loader --------
def load_profile_config(path: str, profile: str) -> dict:
    """
    Load a profile from YAML.

    Supports BOTH layouts:
      A) Top-level profiles:
         crypto_1h:
           watch: [...]
      B) Nested under 'profiles':
         profiles:
           crypto_1h:
             watch: [...]
    """
    import yaml, os

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Choose namespace that actually contains profiles
    if isinstance(data, dict) and "profiles" in data and isinstance(data["profiles"], dict):
        space = data["profiles"]
    else:
        space = data

    if profile not in space:
        raise RuntimeError(f"Profile '{profile}' not found in {path}")

    cfg = space.get(profile) or {}

    # Optional: expand any ${ENV_VAR} values in strings
    def _expand(v):
        if isinstance(v, str):
            return os.path.expandvars(v)
        if isinstance(v, list):
            return [_expand(x) for x in v]
        if isinstance(v, dict):
            return {k: _expand(val) for k, val in v.items()}
        return v

    return _expand(cfg)
# -------------------------------


def _load_default_config() -> dict:
    """Load configuration overrides from ``config.yaml`` if present."""
    path = ROOT / "config.yaml"
    if yaml is None or not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}

def run_cycle(watch, size, grace, risk, equity,
              force=False, interval="1d", adx=15, tz="Europe/Dublin",

              ema_fast=12, ema_slow=26, macd_signal=9,
              ml_model: "PriceDirectionModel | None" = None, ml_threshold: float = 0.6,
              max_trades=999, intervals="", interval_weights=None, vote=False, use_params=False,

              max_portfolio_risk=0.02, cooldown_min=30,
              cap_crypto=2, cap_equity=2, cap_per_ticker=1,
              risk_budget_crypto=0.01, risk_budget_equity=0.01,
              class_caps=None, class_risk_budget=None):

    # Market hours gate (skip if equity market closed unless it's crypto-only or --force)
    if not force and not (all(is_crypto(t) for t in watch) or market_open()):
        log.info("Market closed – skipping cycle.")
        return

    try:
        now_local = dt.datetime.now(ZoneInfo(tz)); tz_label = tz
    except Exception:
        now_local = dt.datetime.now(timezone.utc); tz_label = "UTC"

    # Rank and fetch data for the base interval
    tickers = top_n(watch, size)
    end = dt.date.today().isoformat()
    lookback_days = _max_lookback_days(interval)
    start = (dt.date.today() - dt.timedelta(days=lookback_days)).isoformat()
    price = get_price_data(tickers, start, end, interval=interval)
    base_sig = generate_signals(
        price,
        adx_threshold=adx,
        fast_span=ema_fast,
        slow_span=ema_slow,
        macd_signal=macd_signal,
        ml_model=ml_model,
        ml_threshold=ml_threshold,
    )
    log.info("Signals: %s", base_sig)

    # Multi-interval voting (accept list OR string)
    if vote and intervals:
        weights = _parse_interval_weights(interval_weights)
        maps = {interval: base_sig}
        for itv in _normalize_intervals(intervals):
            if itv in maps:
                continue
            try:
                lb_v = _max_lookback_days(itv)
                start_v = (dt.date.today() - dt.timedelta(days=lb_v)).isoformat()
                price_v = get_price_data(tickers, start_v, end, interval=itv)

                maps[itv] = generate_signals(
                    price_v,
                    adx_threshold=adx,
                    fast_span=ema_fast,
                    slow_span=ema_slow,
                    macd_signal=macd_signal,
                    ml_model=ml_model,
                    ml_threshold=ml_threshold,
                )

            except Exception as e:
                log.error("Voting interval %s failed: %s", itv, e)
        base_sig = vote_signals(maps, weights)

    params = load_params() if use_params else {}
    key_group = ",".join(sorted(watch)) + "|" + interval
    defaults = {
        "adx": adx,
        "sl": 0.02,
        "tp": 0.04,
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

    # Filter candidates by caps and tuned ADX
    for tkr in tickers:
        side = base_sig.get(tkr, "Hold")
        if side == "Hold":
            continue
        tkr = tkr.replace(" ", "").replace("\u00A0", "")
        cls = classify(tkr)

        tuned = tuned_for(tkr, interval, key_group, params, defaults)
        tuned_adx = int(tuned.get("adx", adx))
        try:
            series_adx = _adx(price[tkr]["High"], price[tkr]["Low"], price[tkr]["Close"]).dropna()
            if len(series_adx) and series_adx.iloc[-1] < tuned_adx:
                continue
        except Exception:
            pass

        if per_cls[cls] >= caps.get(cls, default_cap):
            log.info("Cap skip (%s): %s", cls, tkr)
            limits_hit.add("max positions")
            continue
        if per_tkr.get(tkr, 0) >= cap_per_ticker:
            log.info("Cap skip (per-ticker): %s", tkr); continue

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
    if budgets_input:
        specified_total = sum(budgets_input.get(cls, 0.0) for cls in classes)
        unspecified = [c for c in classes if c not in budgets_input]
        remaining_port = max(0.0, max_portfolio_risk - specified_total)
        budget = {cls: budgets_input.get(cls, 0.0) for cls in classes}
        if unspecified:
            per_cls_budget = remaining_port / len(unspecified)
            for c in unspecified:
                budget[c] = per_cls_budget
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
        sl_p = float(tuned.get("sl", defaults["sl"]))
        tp_p = float(tuned.get("tp", defaults["tp"]))
        sl   = round(last * (1 - sl_p) if side == "Buy" else last * (1 + sl_p), 2)
        tp   = round(last * (1 + tp_p) if side == "Buy" else last * (1 - tp_p), 2)

        from SmartCFDTradingAgent.indicators import atr as _atr
        high = price[tkr]["High"].dropna().tail(15)
        low  = price[tkr]["Low"].dropna().tail(15)
        cls_px  = price[tkr]["Close"].dropna().tail(15)
        atr_val = float(_atr(high, low, cls_px).iloc[-1]) if len(cls_px) >= 2 else max(1.0, last*0.01)

        planned_left = max(1, remaining[cls])
        per_trade_budget = max(0.0, remaining_budget[cls]) / planned_left
        per_trade_risk = min(per_trade_budget,  # honor class budget
                             risk)              # honor per-trade cap
        if per_trade_budget <= 0:
            limits_hit.add("risk")
        qty = qty_from_atr(atr_val, equity, per_trade_risk)

        risk_eur = round(per_trade_risk * equity, 2)
        atr_pct = (atr_val / last) * 100.0 if last else 0.0
        if side == "Buy":
            r_multiple = (tp - last) / max(1e-9, (last - sl))
        else:
            r_multiple = (last - tp) / max(1e-9, (sl - last))

        emoji = "🟢" if side == "Buy" else "🔴"
        lines.append(
            f"{emoji} {tkr}  {side} | Px {last:.2f} | SL {sl:.2f} | TP {tp:.2f} | "
            f"Qty≈{qty} | ATR≈{atr_pct:.2f}% | R≈{r_multiple:.2f} | Risk≈€{risk_eur}"
        )
        rows.append({
            "ts": now_iso, "tz": tz_label, "interval": interval, "adx": int(tuned.get("adx", adx)),
            "ticker": tkr, "side": side, "price": round(last,2), "sl": sl, "tp": tp
        })

        remaining_budget[cls] -= per_trade_risk
        remaining[cls] -= 1
        last_state[key] = now_iso

    if len(lines) == 1:
        caps_msg = ", ".join(f"{k}={v}" for k, v in caps.items()) or "none"
        lines.append(
            f"All alerts suppressed by caps/cooldown/filters "
            f"(caps: {caps_msg}, per_ticker={cap_per_ticker}; cooldown={cooldown_min} min)."
        )

    txt = "\n".join(lines)
    safe_send(txt)
    for _ln in lines:
        log.info(_ln)

    if rows:
        write_decision_log(rows)
    _save_last_signals(last_state)

    # Grace delay (gives you time to enter manually if you want)
    time.sleep(max(0, grace))

    # Lightweight backtest preview on the same data slice
    pnl, stats, _ = backtest(price, base_sig, max_hold=5, cost=0.0002,
                             sl=defaults["sl"], tp=defaults["tp"], risk_pct=risk, equity=equity)
    last_cum = pnl["cum_return"].iloc[-1]
    msg = ("Backtest cum return (1yr): "
           f"{last_cum:.2f}x | Sharpe {stats['sharpe']:.2f} | "
           f"Max DD {stats['max_drawdown']:.2%} | Win rate {stats['win_rate']:.2%}")
    safe_send(msg)

    summary = f"Summary: signals={len(base_sig)}, orders={len(rows)}"
    if limits_hit:
        summary += " | limits: " + ",".join(sorted(limits_hit))
    safe_send(summary)
    return pnl, stats, summary

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", nargs="+", help="Symbols (Yahoo): e.g., SPY QQQ or BTC-USD ETH-USD")
    ap.add_argument("--size", type=int, default=5)
    ap.add_argument("--grace", type=int, default=900)
    ap.add_argument("--risk", type=float, default=0.01)
    ap.add_argument("--equity", type=float, default=1000.0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--interval", default="1d")
    ap.add_argument("--adx", type=int, default=15)
    ap.add_argument("--ema-fast", type=int, default=12)
    ap.add_argument("--ema-slow", type=int, default=26)
    ap.add_argument("--macd-signal", type=int, default=9)
    ap.add_argument("--tz", default="Europe/Dublin")
    ap.add_argument("--ml-model", help="Path to trained ML model for signal blending")
    ap.add_argument("--ml-threshold", type=float, default=0.6, help="Probability threshold for ML override")
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
    # Voting / params
    ap.add_argument("--intervals", default="")
    ap.add_argument("--interval-weights", default="", help="Weights for voting intervals, e.g. 15m=1,1h=2")
    ap.add_argument("--vote", action="store_true")
    ap.add_argument("--use-params", action="store_true")
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

    if args.show_decisions > 0:
        rows = read_last_decisions(args.show_decisions)
        msg = format_decisions(rows); print(msg)
        if args.to_telegram: safe_send(msg)
        return
    if args.daily_summary:
        send_daily_summary(args.tz); return

    # If a config file is provided, load it and run with that profile (CLI still allows --force)
    if args.config:
        cfg = load_profile_config(args.config, args.profile)
        watch = cfg.get("watch", [])
        if isinstance(watch, str):
            watch = watch.split()
        if not watch:
            print("Config missing 'watch' list."); sys.exit(2)
        model_cfg = None
        ml_path = cfg.get("ml_model", args.ml_model)
        if ml_path:
            try:
                from SmartCFDTradingAgent.ml_models import PriceDirectionModel
                model_cfg = PriceDirectionModel.load(ml_path)
            except Exception as e:
                log.error("Failed to load ML model from config: %s", e)
        run_cycle(
            watch=watch,
            size=int(cfg.get("size", args.size)),
            grace=int(cfg.get("grace", args.grace)),
            risk=float(cfg.get("risk", args.risk)),
            equity=float(cfg.get("equity", args.equity)),
            force=(args.force or bool(cfg.get("force", False))),
            interval=cfg.get("interval", args.interval),
            adx=int(cfg.get("adx", args.adx)),
            tz=cfg.get("tz", args.tz),
            ema_fast=int(cfg.get("ema_fast", args.ema_fast)),
            ema_slow=int(cfg.get("ema_slow", args.ema_slow)),
            macd_signal=int(cfg.get("macd_signal", args.macd_signal)),
            ml_model=model_cfg,
            ml_threshold=float(cfg.get("ml_threshold", args.ml_threshold)),
            max_trades=int(cfg.get("max_trades", args.max_trades)),
            intervals=cfg.get("intervals", args.intervals),  # list or string — handled inside run_cycle
            interval_weights=cfg.get("interval_weights", args.interval_weights),
            vote=bool(cfg.get("vote", args.vote)),
            use_params=bool(cfg.get("use_params", args.use_params)),
            max_portfolio_risk=float(cfg.get("max_portfolio_risk", args.max_portfolio_risk)),
            cooldown_min=int(cfg.get("cooldown_min", args.cooldown_min)),
            cap_crypto=int(cfg.get("cap_crypto", args.cap_crypto)),
            cap_equity=int(cfg.get("cap_equity", args.cap_equity)),
            cap_per_ticker=int(cfg.get("cap_per_ticker", args.cap_per_ticker)),
            risk_budget_crypto=float(cfg.get("risk_budget_crypto", args.risk_budget_crypto)),
            risk_budget_equity=float(cfg.get("risk_budget_equity", args.risk_budget_equity)),
            class_caps=_parse_class_caps(cfg.get("class_caps", args.class_caps)),
            class_risk_budget=_parse_interval_weights(cfg.get("class_risk_budget", args.class_risk_budget)),
        )
        return

    if not args.watch:
        print("Error: --watch is required for normal run.")
        sys.exit(2)

    model = None
    if args.ml_model:
        try:
            from SmartCFDTradingAgent.ml_models import PriceDirectionModel
            model = PriceDirectionModel.load(args.ml_model)
        except Exception as e:
            log.error("Failed to load ML model: %s", e)

    try:
        run_cycle(
            watch=args.watch,
            size=args.size,
            grace=args.grace,
            risk=args.risk,
            equity=args.equity,
            force=args.force,
            interval=args.interval,
            adx=args.adx,
            tz=args.tz,
            ema_fast=args.ema_fast,
            ema_slow=args.ema_slow,
            macd_signal=args.macd_signal,
            ml_model=model,
            ml_threshold=args.ml_threshold,
            max_trades=args.max_trades,
            intervals=args.intervals,
            interval_weights=args.interval_weights,
            vote=args.vote,
            use_params=args.use_params,
            max_portfolio_risk=args.max_portfolio_risk,
            cooldown_min=args.cooldown_min,
            cap_crypto=args.cap_crypto,
            cap_equity=args.cap_equity,
            cap_per_ticker=args.cap_per_ticker,
            risk_budget_crypto=args.risk_budget_crypto,
            risk_budget_equity=args.risk_budget_equity,
            class_caps=_parse_class_caps(args.class_caps),
            class_risk_budget=_parse_interval_weights(args.class_risk_budget),
        )

    except Exception as e:
        log.exception("Pipeline crashed: %s", e)
        safe_send(f"⚠️ SmartCFD crashed\n{e}")

if __name__ == "__main__":
    main()
