from __future__ import annotations

import argparse, datetime as dt, json, sqlite3
import logging
from pathlib import Path
import pandas as pd
from SmartCFDTradingAgent.data_loader import get_price_data
from SmartCFDTradingAgent.indicators import ema, macd, adx
from SmartCFDTradingAgent.utils import trade_logger
from SmartCFDTradingAgent.utils.logger import get_logger

try:  # optional dependency
    from SmartCFDTradingAgent.ml_models import PriceDirectionModel
except Exception:  # pragma: no cover - model training optional
    PriceDirectionModel = None  # type: ignore

STORE = Path(__file__).resolve().parent / "storage"
STORE.mkdir(exist_ok=True)

log = logging.getLogger(__name__)


log = get_logger()


def _tz_naive_index(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    try:
        return idx.tz_localize(None) if getattr(idx, "tz", None) is not None else idx
    except Exception:
        return idx


def score_segment(df_tkr: pd.DataFrame, adx_th: int, sl=0.02, tp=0.04, ema_fast=12, ema_slow=26) -> float:
    """Very fast pseudo-backtest score on a price segment."""
    high, low, close = df_tkr["High"], df_tkr["Low"], df_tkr["Close"]
    rets = close.pct_change().fillna(0.0)
    f, s = ema(close, ema_fast), ema(close, ema_slow)
    m = macd(close)
    a = adx(high, low, close).fillna(0)
    pos = 0
    score = 0.0
    hold = 0
    for i in range(1, len(close)):
        hist = m["hist"].iloc[i]
        cond_buy = (f.iloc[i] > s.iloc[i]) and (hist > 0) and (a.iloc[i] >= adx_th)
        cond_sell = (f.iloc[i] < s.iloc[i]) and (hist < 0) and (a.iloc[i] >= adx_th)
        sig = 1 if cond_buy else (-1 if cond_sell else 0)
        if pos == 0 and sig != 0:
            pos = sig
            hold = 0
            score -= 0.0002  # entry cost
            continue
        if pos != 0:
            hold += 1
            r = rets.iloc[i] * pos
            score += r
            if r <= -sl or r >= tp or hold >= 5:
                pos = 0
                score -= 0.0002  # exit cost
    return float(score)


def make_monthly_windows(idx: pd.DatetimeIndex, train_months=6, test_months=1):
    """Yield (train_start, train_end, test_start, test_end) date tuples."""
    if len(idx) == 0:
        return
    idx = _tz_naive_index(idx)
    first = idx.min().to_period("M").to_timestamp()
    last = idx.max().to_period("M").to_timestamp() + pd.offsets.MonthEnd(1)
    cur = first
    while True:
        tr_start = cur
        tr_end = tr_start + pd.offsets.MonthEnd(train_months)
        te_start = tr_end
        te_end = te_start + pd.offsets.MonthEnd(test_months)
        if te_end > last:
            break
        yield (tr_start, tr_end, te_start, te_end)
        cur = cur + pd.offsets.MonthBegin(test_months)


def optimize_walk_forward(df: pd.DataFrame, train_months=6, test_months=1):
    """Evaluate each param combo across rolling folds and return the combo with the best average TEST score."""
    adx_grid = [8, 10, 12, 15, 20]
    sl_grid = [0.015, 0.02, 0.03]
    tp_grid = [0.03, 0.04, 0.06]
    ema_fast_grid = [8, 12]
    ema_slow_grid = [20, 26]

    combos = [
        (adx_th, sl, tp, f, s)
        for adx_th in adx_grid
        for sl in sl_grid
        for tp in tp_grid
        for f in ema_fast_grid
        for s in ema_slow_grid
    ]

    results: dict[tuple, list[float]] = {c: [] for c in combos}

    idx_union = df.index
    for (tr_start, tr_end, te_start, te_end) in make_monthly_windows(idx_union, train_months, test_months):
        best_combo, best_train = None, -1e9
        seg_train = df.loc[(df.index >= tr_start) & (df.index < tr_end)]
        seg_test = df.loc[(df.index >= te_start) & (df.index < te_end)]
        if len(seg_train) < 50 or len(seg_test) < 20:
            continue
        for c in combos:
            adx_th, sl, tp, f, s = c
            tr_sc = score_segment(seg_train, adx_th, sl, tp, f, s)
            if tr_sc > best_train:
                best_train, best_combo = tr_sc, c
        if best_combo is not None:
            adx_th, sl, tp, f, s = best_combo
            te_sc = score_segment(seg_test, adx_th, sl, tp, f, s)
            results[best_combo].append(te_sc)

    best_c, best_avg = None, -1e9
    for c, lst in results.items():
        if lst:
            avg = sum(lst) / len(lst)
            if avg > best_avg:
                best_avg, best_c = avg, c

    if best_c is None:
        return {"adx": 12, "sl": 0.02, "tp": 0.04, "ema_fast": 12, "ema_slow": 26, "wf_avg": 0.0, "folds": 0}
    adx_th, sl, tp, f, s = best_c
    return {
        "adx": adx_th,
        "sl": sl,
        "tp": tp,
        "ema_fast": f,
        "ema_slow": s,
        "wf_avg": round(best_avg, 6),
        "folds": len(results[best_c]),
    }


def retrain_from_trade_log(years: int = 1, interval: str = "1d") -> None:
    """Rebuild walk-forward params and retrain the ML model from trade logs."""
    db_path = trade_logger.DB_PATH
    store = db_path.parent
    if not db_path.exists():
        return

    stamp = store / "last_retrain.txt"
    try:
        if stamp.exists():
            mtime = dt.datetime.fromtimestamp(stamp.stat().st_mtime)
            if (dt.datetime.utcnow() - mtime).total_seconds() < 24 * 3600:
                return
    except Exception:
        pass

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT ticker FROM trades")
        tickers = [r[0] for r in cur.fetchall() if r and r[0]]
    finally:
        conn.close()
    if not tickers:
        return

    end = dt.date.today().isoformat()
    start = (dt.date.today() - dt.timedelta(days=365 * years)).isoformat()
    df = get_price_data(tickers, start, end, interval=interval)

    params_path = store / "params.json"
    try:
        obj = json.loads(params_path.read_text(encoding="utf-8")) if params_path.exists() else {}
    except Exception:
        obj = {}

    if isinstance(df.columns, pd.MultiIndex):
        for t in tickers:
            try:
                one = df[t].dropna(how="all")
            except Exception:
                continue
            if len(one) < 80:
                continue
            best = optimize_walk_forward(one)
            obj[f"{t}|{interval}"] = best
    else:
        best = optimize_walk_forward(df)
        if tickers:
            obj[f"{tickers[0]}|{interval}"] = best

    try:
        params_path.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    except Exception:
        pass

    if PriceDirectionModel is not None:
        try:
            if isinstance(df.columns, pd.MultiIndex):
                close = df.xs("Close", level=1, axis=1).mean(axis=1)
            else:
                close = df["Close"]
            model = PriceDirectionModel()
            model.fit(close.to_frame("Close"))
            model.save(store / "ml_model.pkl")
        except Exception:
            pass

    try:
        stamp.write_text(dt.datetime.utcnow().isoformat(), encoding="utf-8")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", nargs="+", required=True)
    ap.add_argument("--interval", default="1d")
    ap.add_argument("--years", type=int, default=3)
    ap.add_argument("--train-months", type=int, default=6)
    ap.add_argument("--test-months", type=int, default=1)
    ap.add_argument("--per-ticker", action="store_true", help="Save best params per TICKER|interval instead of group key")
    args = ap.parse_args()

    end = dt.date.today().isoformat()
    start = (dt.date.today() - dt.timedelta(days=365 * args.years)).isoformat()
    df = get_price_data(args.watch, start, end, interval=args.interval)

    params_path = STORE / "params.json"
    try:
        obj = json.loads(params_path.read_text(encoding="utf-8")) if params_path.exists() else {}
    except Exception:
        obj = {}

    if isinstance(df.columns, pd.MultiIndex) and args.per_ticker:
        tickers = sorted({c[0] for c in df.columns})
        for t in tickers:
            one = df[t].dropna(how="all")
            if len(one) < 80:
                continue
            best = optimize_walk_forward(one, args.train_months, args.test_months)
            key = f"{t}|{args.interval}"
            obj[key] = best
            log.info("Walk-forward (per-ticker) saved: %s => %s", key, best)
    else:
        best = optimize_walk_forward(df, args.train_months, args.test_months)
        key = ",".join(sorted(args.watch)) + "|" + args.interval
        obj[key] = best
        log.info("Walk-forward (group) saved: %s => %s", key, best)

    params_path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

