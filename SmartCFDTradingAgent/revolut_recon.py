from __future__ import annotations
import argparse, csv, math, datetime as dt
import logging
from pathlib import Path
import pandas as pd

from SmartCFDTradingAgent.utils.logger import get_logger

ROOT = Path(__file__).resolve().parent
STORE = ROOT / "storage"
DECISIONS = STORE / "decision_log.csv"


log = logging.getLogger(__name__)


def _load_decisions(day: str) -> pd.DataFrame:
    if not DECISIONS.exists():
        raise SystemExit("decision_log.csv not found.")
    df = pd.read_csv(DECISIONS)
    df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
    df["date"] = df["ts"].dt.date.astype(str)
    return df[df["date"] == day].copy()

def _load_revolut_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Try to normalize; Revolut exports vary. We look for these logical fields.
    candidates_date = [c for c in df.columns if c.lower() in ("date", "time", "timestamp", "opened at")]
    candidates_ticker = [c for c in df.columns if "ticker" in c.lower() or "instrument" in c.lower() or "symbol" in c.lower()]
    candidates_qty = [c for c in df.columns if "quantity" in c.lower() or "qty" in c.lower() or "units" in c.lower()]
    candidates_price = [c for c in df.columns if "price" in c.lower()]
    if not (candidates_date and candidates_ticker and candidates_qty and candidates_price):
        raise SystemExit("CSV columns not recognized. Please export detailed trades CSV from Revolut.")
    c_date, c_tkr, c_qty, c_px = candidates_date[0], candidates_ticker[0], candidates_qty[0], candidates_price[0]
    df["_ts_raw"] = df[c_date].astype(str)
    # Try parse multiple formats
    df["ts"] = pd.to_datetime(df["_ts_raw"], errors="coerce", utc=True).dt.tz_convert("Europe/Dublin").dt.tz_localize(None)
    df["ticker"] = df[c_tkr].astype(str).str.replace(" ", "").str.replace("\u00A0", "", regex=False)
    df["qty"] = pd.to_numeric(df[c_qty], errors="coerce")
    df["price"] = pd.to_numeric(df[c_px], errors="coerce")
    df = df.dropna(subset=["ts", "ticker", "qty", "price"])
    df["date"] = df["ts"].dt.date.astype(str)
    df["side"] = df["qty"].apply(lambda q: "Buy" if q > 0 else ("Sell" if q < 0 else "Hold"))
    return df

def _nearest_trade(trades: pd.DataFrame, tkr: str, side: str, t_ref: pd.Timestamp, window_min: int):
    subset = trades[(trades["ticker"] == tkr) & (trades["side"] == side)]
    if subset.empty: return None
    subset["diff_min"] = (subset["ts"] - t_ref).abs().dt.total_seconds() / 60.0
    subset = subset[subset["diff_min"] <= window_min]
    if subset.empty: return None
    return subset.sort_values("diff_min").iloc[0]

def recon(csv_path: str, day: str, window_min: int = 90, to_telegram: bool = False) -> Path:
    from SmartCFDTradingAgent.utils.telegram import send as tg_send
    dec = _load_decisions(day)
    trd = _load_revolut_csv(csv_path)
    trd = trd[trd["date"] == day]
    rows = []
    matched = 0
    for _, r in dec.iterrows():
        tkr, side = r["ticker"], r["side"]
        t_ref = pd.to_datetime(r["ts"])
        hit = _nearest_trade(trd, tkr, side, t_ref, window_min)
        if hit is None:
            rows.append({**r.to_dict(), "match": "NO", "ex_price": "", "ex_time": "", "slip": ""})
        else:
            matched += 1
            slip = float(hit["price"]) - float(r["price"])
            rows.append({**r.to_dict(), "match": "YES", "ex_price": round(float(hit["price"]), 4),
                         "ex_time": str(hit["ts"]), "slip": round(slip, 4)})
    out = STORE / f"recon_{day}.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    summary = f"Revolut Reconciliation {day}\nDecisions: {len(dec)}  Matched: {matched}\nFile: {out.name}"
    log.info(summary)
    if to_telegram:
        try: tg_send(summary)
        except Exception: pass
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to Revolut trades CSV export")
    ap.add_argument("--day", required=False, help="YYYY-MM-DD (default: today Europe/Dublin)")
    ap.add_argument("--window-min", type=int, default=90, help="Match window in minutes")
    ap.add_argument("--to-telegram", action="store_true", help="Send summary to Telegram")
    args = ap.parse_args()
    if not args.day:
        from zoneinfo import ZoneInfo
        day = dt.datetime.now(ZoneInfo("Europe/Dublin")).date().isoformat()
    else:
        day = args.day
    out = recon(args.csv, day, args.window_min, args.to_telegram)
    log.info("Saved %s", out)

if __name__ == "__main__":
    main()
