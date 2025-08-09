from __future__ import annotations
import argparse, json, datetime as dt
from pathlib import Path
import numpy as np, pandas as pd
from SmartCFDTradingAgent.data_loader import get_price_data
from SmartCFDTradingAgent.indicators import ema, macd, adx

STORE = Path(__file__).resolve().parent / "storage"
STORE.mkdir(exist_ok=True)

def backtest_simple(df: pd.DataFrame, adx_th: int, sl=0.02, tp=0.04, max_hold=5,
                    ema_fast=12, ema_slow=26) -> float:
    close = df.xs("Close", level=1, axis=1)
    rets = close.pct_change().fillna(0.0)
    score = 0.0
    for t in close.columns:
        c = close[t]
        f, s = ema(c, ema_fast), ema(c, ema_slow)
        m = macd(c)
        a = adx(df[t]["High"], df[t]["Low"], df[t]["Close"]).fillna(0)
        pos = 0; hold=0
        for i in range(1, len(c)):
            hist = m["hist"].iloc[i]
            cond_buy  = (f.iloc[i] > s.iloc[i]) and (hist > 0) and (a.iloc[i] >= adx_th)
            cond_sell = (f.iloc[i] < s.iloc[i]) and (hist < 0) and (a.iloc[i] >= adx_th)
            sig = 1 if cond_buy else (-1 if cond_sell else 0)
            if pos == 0 and sig != 0:
                pos = sig; hold = 0; score -= 0.0002; continue
            if pos != 0:
                hold += 1
                r = rets.iloc[i][t] * pos
                score += r
                if r <= -sl or r >= tp or hold >= max_hold:
                    pos = 0; score -= 0.0002
    return float(score)

def optimize(tickers, years=2, interval="1d"):
    end = dt.date.today().isoformat()
    start = (dt.date.today() - dt.timedelta(days=365*years)).isoformat()
    df = get_price_data(tickers, start, end, interval=interval)
    adx_grid = [8, 10, 12, 15, 20]
    sl_grid  = [0.015, 0.02, 0.03]
    tp_grid  = [0.03, 0.04, 0.06]
    fast_grid= [8, 12]
    slow_grid= [20, 26]
    best = {"score": -1e9}
    for adx_th in adx_grid:
        for sl in sl_grid:
            for tp in tp_grid:
                for f in fast_grid:
                    for s in slow_grid:
                        score = backtest_simple(df, adx_th, sl, tp, max_hold=5, ema_fast=f, ema_slow=s)
                        if score > best["score"]:
                            best = {"adx": adx_th, "sl": sl, "tp": tp, "ema_fast": f, "ema_slow": s, "score": score}
    return best

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", nargs="+", required=True)
    ap.add_argument("--interval", default="1d")
    ap.add_argument("--years", type=int, default=2)
    args = ap.parse_args()
    best = optimize(args.watch, years=args.years, interval=args.interval)
    params_path = STORE / "params.json"
    try:
        obj = json.loads(params_path.read_text(encoding="utf-8")) if params_path.exists() else {}
    except Exception:
        obj = {}
    key = ",".join(sorted(args.watch)) + "|" + args.interval
    obj[key] = best
    params_path.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    print("Saved params to", params_path, "for key", key, "=>", best)

if __name__ == "__main__":
    main()
