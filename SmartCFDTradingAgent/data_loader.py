from __future__ import annotations

import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, List

import pandas as pd
import yfinance as yf

from SmartCFDTradingAgent.utils.logger import get_logger

INTRADAY = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}
FIELDS_ORDER = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]

# --- Configurable defaults ---
DEFAULT_WORKERS = int(os.getenv("DATA_WORKERS", "4"))
DEFAULT_CACHE_EXPIRY = float(os.getenv("DATA_CACHE_EXPIRY", "3600"))  # seconds
CACHE_DIR = Path(
    os.getenv(
        "DATA_CACHE_DIR",
        str(Path(__file__).resolve().parent / "storage" / "cache"),
    )
)

log = get_logger()


def _cache_path(key: str) -> Path:
    """Return the cache file path for a given key."""
    h = hashlib.md5(key.encode()).hexdigest()
    return CACHE_DIR / f"{h}.pkl"


def _load_cache(key: str, expire: float) -> pd.DataFrame | None:
    p = _cache_path(key)
    if not p.exists():
        return None
    try:
        if expire > 0 and time.time() - p.stat().st_mtime > expire:
            p.unlink(missing_ok=True)
            return None
        return pd.read_pickle(p)
    except Exception:
        return None


def _save_cache(key: str, df: pd.DataFrame) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        df.to_pickle(_cache_path(key))
    except Exception:
        pass


def _normalize_to_ticker_field(df: pd.DataFrame, tickers: List[str]) -> pd.DataFrame:
    """Normalize columns to MultiIndex [ticker, field] regardless of yfinance layout."""
    if df is None or df.empty:
        return df

    if not isinstance(df.columns, pd.MultiIndex):
        # Single-index: wrap to [ticker, field] if single ticker
        if len(tickers) == 1:
            return pd.concat({tickers[0]: df}, axis=1)
        return df

    lvl0 = df.columns.get_level_values(0)
    lvl1 = df.columns.get_level_values(1)
    set0, set1 = set(lvl0), set(lvl1)
    tset = set(tickers)

    if tset & set0:
        out = df.copy()
    elif tset & set1:
        out = df.swaplevel(0, 1, axis=1).sort_index(axis=1)
    else:
        out = df

    try:
        new_cols = []
        for t in tickers:
            if t in out.columns.get_level_values(0):
                avail = [f for f in FIELDS_ORDER if (t, f) in out.columns]
                if avail:
                    for f in avail:
                        new_cols.append((t, f))
        if new_cols:
            out = out.loc[:, pd.MultiIndex.from_tuples(new_cols)]
    except Exception:
        pass

    return out


def _download(
    tickers_or_symbol,
    *,
    period: str | None = None,
    start: str | None = None,
    end: str | None = None,
    interval: str = "1d",
    threads: bool = True,
):
    return yf.download(
        tickers_or_symbol,
        period=period,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=False,
        prepost=False,
        actions=False,
        threads=threads,
        progress=False,
        # NOTE: don't pass show_errors (not supported in your yfinance)
    )


def get_price_data(
    tickers: Iterable[str],
    start: str,
    end: str,
    interval: str = "1d",
    max_tries: int = 3,
    pause: float = 1.0,
    workers: int | None = None,
    cache_expire: float | None = None,
) -> pd.DataFrame:
    """
    Robust downloader with retries and shape normalization.
    INTRADAY: per-ticker only with tested combos (no batch).
    DAILY+: batch then per-ticker salvage.
    Returns MultiIndex columns [ticker, field].
    """
    tickers = list(dict.fromkeys(tickers))
    iv = (interval or "1d").lower()

    # ---------- Intraday path (per-ticker only) ----------
    if iv in INTRADAY:
        # Use the exact combos that worked on your machine.
        combos = [
            ("7d", "1h"),
            ("30d", "60m"),
            ("30d", "30m"),
            ("7d", "15m"),
        ]

        workers = workers or DEFAULT_WORKERS
        cache_expire = cache_expire if cache_expire is not None else DEFAULT_CACHE_EXPIRY

        frames: list[pd.DataFrame] = []
        missing: list[str] = []
        cache_hits = 0

        def _worker(t: str):
            for per, interval_try in combos:
                key = f"{t}|{per}|{interval_try}|{start}|{end}"
                cached = _load_cache(key, cache_expire)
                if cached is not None:
                    return t, cached, True
                for attempt in range(1, max_tries + 1):
                    try:
                        d1 = _download(t, period=per, interval=interval_try, threads=False)
                        d1 = _normalize_to_ticker_field(d1, [t])
                        if d1 is not None and not d1.dropna(how="all").empty:
                            _save_cache(key, d1)
                            return t, d1, False
                    except Exception:
                        pass
                    time.sleep(pause * attempt)
            return t, None, False

        start_t = time.time()
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = {ex.submit(_worker, t): t for t in tickers}
            for fut in as_completed(futures):
                t, df, hit = fut.result()
                if df is not None:
                    frames.append(df)
                else:
                    missing.append(t)
                if hit:
                    log.info("Cache hit for %s", t)
                    cache_hits += 1

        elapsed = time.time() - start_t
        log.info(
            "Intraday fetch completed in %.2fs for %d tickers (%d cache hits, %d workers)",
            elapsed,
            len(tickers),
            cache_hits,
            workers,
        )

        if frames:
            out = pd.concat(frames, axis=1).sort_index()
            if missing:
                log.warning("%d Failed downloads:\n%s", len(missing), missing)
            return out

        # nothing worked
        raise RuntimeError(f"No data returned for {missing}.")

    # ---------- Daily/above path ----------
    last_err = None
    for attempt in range(1, max_tries + 1):
        try:
            df = _download(tickers, start=start, end=end, interval=iv, threads=True)
            df = _normalize_to_ticker_field(df, tickers)
            if df is not None and not df.dropna(how="all").empty:
                return df
            raise RuntimeError("No data returned (batch daily).")
        except Exception as e:
            last_err = e
            time.sleep(pause * attempt)

    # Per-ticker salvage for daily
    frames: list[pd.DataFrame] = []
    missing: list[str] = []
    for t in tickers:
        try:
            d1 = _download(t, start=start, end=end, interval=iv, threads=False)
            d1 = _normalize_to_ticker_field(d1, [t])
            if d1 is None or d1.dropna(how="all").empty:
                missing.append(t)
                continue
            frames.append(d1)
        except Exception:
            missing.append(t)

    if frames:
        out = pd.concat(frames, axis=1).sort_index()
        if missing:
            log.warning("%d Failed downloads:\n%s", len(missing), missing)
        return out

    if missing:
        raise RuntimeError(f"No data returned for {missing}.")
    raise RuntimeError(f"Failed to download data: {last_err}")
