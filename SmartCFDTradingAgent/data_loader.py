from __future__ import annotations

import hashlib
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable, List

import pandas as pd
import requests
import yfinance as yf

from SmartCFDTradingAgent.utils.logger import get_logger

INTRADAY = {"1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h"}
FIELDS_ORDER = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]

ALPACA_CRYPTO_EXCHANGES = [ex.strip().upper() for ex in os.getenv("ALPACA_CRYPTO_EXCHANGES", "CBSE").split(",") if ex.strip()]

def _truthy(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}

def _has_alpaca_creds() -> bool:
    return bool(os.getenv("ALPACA_API_KEY") or os.getenv("APCA_API_KEY_ID"))

def use_alpaca_crypto() -> bool:
    """Return True if crypto data should be fetched from Alpaca.

    Prefers explicit flag ``USE_ALPACA_CRYPTO=1``; otherwise auto-enables when
    Alpaca credentials are present in the environment (loaded via dotenv).
    """
    return _truthy("USE_ALPACA_CRYPTO") or _has_alpaca_creds()

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


def _quiet_yf_logs() -> None:
    """Reduce noise from yfinance/urllib3 when not using Alpaca.

    Controlled by env var YF_SILENT (defaults to on).
    """
    try:
        silent = os.getenv("YF_SILENT", "1").strip().lower() in {"1", "true", "yes", "on"}
        if not silent:
            return
        logging.getLogger("yfinance").setLevel(logging.ERROR)
        logging.getLogger("urllib3").setLevel(logging.ERROR)
    except Exception:
        pass


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



def _is_crypto_symbol(ticker: str) -> bool:
    return '-' in (ticker or '')


def _ensure_utc(ts: pd.Timestamp) -> pd.Timestamp:
    if ts.tzinfo is None:
        return ts.tz_localize('UTC')
    return ts.tz_convert('UTC')


def _alpaca_timeframe(interval: str):
    interval = (interval or '1h').lower()
    try:
        from alpaca_trade_api.rest import TimeFrame, TimeFrameUnit
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError('alpaca-trade-api package is required for Alpaca data provider') from exc
    mapping: dict[str, TimeFrame] = {
        '1m': TimeFrame(1, TimeFrameUnit.Minute),
        '5m': TimeFrame(5, TimeFrameUnit.Minute),
        '15m': TimeFrame(15, TimeFrameUnit.Minute),
        '30m': TimeFrame(30, TimeFrameUnit.Minute),
        '1h': TimeFrame(1, TimeFrameUnit.Hour),
        '60m': TimeFrame(1, TimeFrameUnit.Hour),
        '1d': TimeFrame(1, TimeFrameUnit.Day),
    }
    if interval not in mapping:
        raise ValueError(f'Interval {interval} not supported by Alpaca crypto feed.')
    return mapping[interval]


def _get_crypto_data_alpaca(tickers: list[str], start: str, end: str, interval: str) -> pd.DataFrame:
    try:
        import alpaca_trade_api as tradeapi
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError('alpaca-trade-api package required for Alpaca crypto loader') from exc

    key = os.getenv('ALPACA_API_KEY') or os.getenv('APCA_API_KEY_ID')
    secret = os.getenv('ALPACA_API_SECRET') or os.getenv('APCA_API_SECRET_KEY')
    base_url = os.getenv('APCA_API_BASE_URL', 'https://paper-api.alpaca.markets')
    if not key or not secret:
        raise RuntimeError('Alpaca API credentials missing (ALPACA_API_KEY / ALPACA_API_SECRET)')

    client = tradeapi.REST(key, secret, base_url, api_version='v2')

    timeframe = _alpaca_timeframe(interval)
    start_ts = _ensure_utc(pd.Timestamp(start))
    end_ts = _ensure_utc(pd.Timestamp(end)) + pd.Timedelta(days=1)

    symbols = [ticker.replace('-', '/').upper() for ticker in tickers]
    exchanges = ALPACA_CRYPTO_EXCHANGES or None
    bars = client.get_crypto_bars(symbols, timeframe, start_ts.isoformat(), end_ts.isoformat(), limit=10000)
    df = bars.df
    if df is None or df.empty:
        raise RuntimeError(f'No data returned for {tickers} via Alpaca.')

    data = df.reset_index()
    data['symbol'] = data['symbol'].str.replace('/', '-').str.upper()
    data['timestamp'] = pd.to_datetime(data['timestamp'])
    if getattr(data['timestamp'].dt, 'tz', None) is not None:
        data['timestamp'] = data['timestamp'].dt.tz_convert('UTC').dt.tz_localize(None)
    else:
        data['timestamp'] = data['timestamp'].dt.tz_localize(None)
    data = data.rename(columns={
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume',
    })
    frames: list[pd.DataFrame] = []
    for symbol, group in data.groupby('symbol'):
        sub = group.sort_values('timestamp').set_index('timestamp')[['Open', 'High', 'Low', 'Close', 'Volume']]
        frames.append(pd.concat({symbol: sub}, axis=1))

    if not frames:
        raise RuntimeError(f'No data returned for {tickers} via Alpaca.')
    result = pd.concat(frames, axis=1)
    result = result.sort_index()
    return result


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


_YF_SESSIONS: dict[bool, requests.Session] = {}
_COINBASE_SESSIONS: dict[bool, requests.Session] = {}


def _build_session(
    *,
    user_agent_env: str,
    default_agent: str,
    disable_proxy_env: str | None = None,
    force_direct: bool = False,
    extra_headers: dict[str, str] | None = None,
) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": os.getenv(user_agent_env, default_agent),
        }
    )
    if extra_headers:
        session.headers.update(extra_headers)
    if force_direct or (disable_proxy_env and _truthy(disable_proxy_env)):
        session.trust_env = False
    return session


def _get_yf_session(force_direct: bool = False) -> requests.Session:
    global _YF_SESSIONS
    key = bool(force_direct)
    session = _YF_SESSIONS.get(key)
    if session is None:
        session = _build_session(
            user_agent_env="YF_USER_AGENT",
            default_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            ),
            disable_proxy_env="YF_DISABLE_PROXY" if not force_direct else None,
            force_direct=force_direct,
        )
        _YF_SESSIONS[key] = session
    return session


def _get_coinbase_session(force_direct: bool = False) -> requests.Session:
    global _COINBASE_SESSIONS
    key = bool(force_direct)
    session = _COINBASE_SESSIONS.get(key)
    if session is None:
        session = _build_session(
            user_agent_env="COINBASE_USER_AGENT",
            default_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            ),
            disable_proxy_env="COINBASE_DISABLE_PROXY" if not force_direct else None,
            force_direct=force_direct,
            extra_headers={"Accept": "application/json"},
        )
        _COINBASE_SESSIONS[key] = session
    return session


def _download_history(
    ticker: str,
    *,
    start: str | None,
    end: str | None,
    interval: str,
) -> pd.DataFrame | None:
    """Fallback to ``Ticker.history`` for stubborn Yahoo responses."""

    session = _get_yf_session()
    try:
        history = yf.Ticker(ticker, session=session).history(
            start=start,
            end=end,
            interval=interval,
            auto_adjust=False,
            actions=False,
            prepost=False,
        )
    except requests.exceptions.ProxyError as exc:
        log.warning(
            "Ticker.history proxy request failed for %s: %s – retrying without proxies",
            ticker,
            exc,
        )
        try:
            session = _get_yf_session(force_direct=True)
            history = yf.Ticker(ticker, session=session).history(
                start=start,
                end=end,
                interval=interval,
                auto_adjust=False,
                actions=False,
                prepost=False,
            )
        except Exception as exc2:
            log.debug("Ticker.history direct retry failed for %s: %s", ticker, exc2)
            return None
    except Exception as exc:
        log.debug("Ticker.history failed for %s: %s", ticker, exc)
        return None

    if history is None or history.empty:
        return None

    history.index = pd.to_datetime(history.index)
    history = history.sort_index()
    expected_cols = [c for c in FIELDS_ORDER if c in history.columns]
    if not expected_cols:
        return None

    history = history[expected_cols]
    return pd.concat({ticker: history}, axis=1)


def _download_chart(
    ticker: str,
    *,
    start: str | None,
    end: str | None,
    interval: str,
    cache_expire: float | None = None,
) -> pd.DataFrame | None:
    """Fallback using Yahoo chart API when yfinance helpers fail.

    Returns data normalized to MultiIndex [ticker, field] or ``None`` when
    retrieval fails. Responses are cached using the shared pickle cache so we
    don't spam Yahoo when running multiple retries.
    """

    start_ts = pd.Timestamp(start) if start is not None else None
    end_ts = pd.Timestamp(end) if end is not None else None
    if start_ts is None or end_ts is None:
        return None

    start_ts = _ensure_utc(start_ts)
    end_ts = _ensure_utc(end_ts)
    if end_ts <= start_ts:
        end_ts = start_ts + pd.Timedelta(days=1)

    iv = interval.lower()
    interval_map = {"1h": "60m", "90m": "90m"}
    yahoo_interval = interval_map.get(iv, iv)

    key = f"chart|{ticker}|{yahoo_interval}|{int(start_ts.timestamp())}|{int(end_ts.timestamp())}"
    if cache_expire is not None:
        cached = _load_cache(key, cache_expire)
        if cached is not None:
            return cached

    params = {
        "period1": int(start_ts.timestamp()),
        "period2": int(end_ts.timestamp()),
        "interval": yahoo_interval,
        "includePrePost": "false",
        "events": "history",
    }

    session = _get_yf_session()
    timeout = float(os.getenv("YF_TIMEOUT", "10"))
    try:
        resp = session.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
            params=params,
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.exceptions.ProxyError as exc:
        log.warning(
            "Yahoo chart API via proxy failed for %s: %s – retrying without proxies",
            ticker,
            exc,
        )
        try:
            session = _get_yf_session(force_direct=True)
            resp = session.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
                params=params,
                timeout=timeout,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc2:
            log.debug("Yahoo chart API direct retry failed for %s: %s", ticker, exc2)
            return None
    except Exception as exc:
        log.debug("Yahoo chart API request failed for %s: %s", ticker, exc)
        return None

    result = payload.get("chart", {}).get("result") or []
    if not result:
        return None

    result = result[0]
    timestamps = result.get("timestamp")
    indicators = result.get("indicators", {})
    quotes = (indicators.get("quote") or [{}])[0]
    adjcloses = (indicators.get("adjclose") or [{}])[0]
    if not timestamps:
        return None

    index = pd.to_datetime(timestamps, unit="s", utc=True).tz_convert(None)
    frame = pd.DataFrame(
        {
            "Open": quotes.get("open"),
            "High": quotes.get("high"),
            "Low": quotes.get("low"),
            "Close": quotes.get("close"),
            "Adj Close": adjcloses.get("adjclose"),
            "Volume": quotes.get("volume"),
        },
        index=index,
    )

    frame = frame.dropna(how="all")
    if frame.empty:
        return None

    # Ensure chronological order and expected column subset
    frame = frame.sort_index()
    expected_cols = [c for c in FIELDS_ORDER if c in frame.columns]
    frame = frame[expected_cols]

    out = pd.concat({ticker: frame}, axis=1)
    if cache_expire is not None:
        _save_cache(key, out)
    return out


_COINBASE_GRANULARITY = {
    "1m": 60,
    "2m": 120,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "60m": 3600,
    "90m": 5400,
    "1h": 3600,
    "1d": 86400,
}


def _download_coinbase(
    ticker: str,
    *,
    start: str | None,
    end: str | None,
    interval: str,
    cache_expire: float | None = None,
) -> pd.DataFrame | None:
    """Fallback using Coinbase public candles endpoint.

    Coinbase limits each request to 300 candles; this function automatically
    chunks the requested timerange and stitches responses together. Results are
    cached using the shared pickle cache so we do not overwhelm the API.
    """

    granularity = _COINBASE_GRANULARITY.get(interval.lower())
    if granularity is None:
        return None

    start_ts = pd.Timestamp(start) if start is not None else None
    end_ts = pd.Timestamp(end) if end is not None else None
    if start_ts is None or end_ts is None:
        return None

    start_ts = _ensure_utc(start_ts)
    end_ts = _ensure_utc(end_ts)
    if end_ts <= start_ts:
        end_ts = start_ts + pd.Timedelta(seconds=granularity)

    key = (
        f"coinbase|{ticker}|{granularity}|"
        f"{int(start_ts.timestamp())}|{int(end_ts.timestamp())}"
    )
    if cache_expire is not None:
        cached = _load_cache(key, cache_expire)
        if cached is not None:
            return cached

    base_url = os.getenv(
        "COINBASE_API_URL", "https://api.exchange.coinbase.com"
    ).rstrip("/")
    product = ticker.upper().replace("_", "-")
    url = f"{base_url}/products/{product}/candles"

    chunk = pd.Timedelta(seconds=granularity * 300)
    current_start = start_ts
    rows: list[dict] = []
    timeout = float(os.getenv("COINBASE_TIMEOUT", "10"))

    session = _get_coinbase_session()

    while current_start < end_ts:
        current_end = min(current_start + chunk, end_ts)
        params = {
            "start": current_start.isoformat(),
            "end": current_end.isoformat(),
            "granularity": granularity,
        }
        try:
            resp = session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            payload = resp.json()
        except requests.exceptions.ProxyError as exc:
            log.warning(
                "Coinbase API via proxy failed for %s [%s - %s]: %s – retrying without proxies",
                ticker,
                current_start,
                current_end,
                exc,
            )
            session = _get_coinbase_session(force_direct=True)
            try:
                resp = session.get(url, params=params, timeout=timeout)
                resp.raise_for_status()
                payload = resp.json()
            except Exception as exc2:
                log.debug(
                    "Coinbase API direct retry failed for %s [%s - %s]: %s",
                    ticker,
                    current_start,
                    current_end,
                    exc2,
                )
                return None
        except Exception as exc:
            log.debug(
                "Coinbase API request failed for %s [%s - %s]: %s",
                ticker,
                current_start,
                current_end,
                exc,
            )
            return None

        if not isinstance(payload, list):
            log.debug("Coinbase API unexpected payload for %s: %s", ticker, payload)
            return None

        for entry in payload:
            if not isinstance(entry, (list, tuple)) or len(entry) < 6:
                continue
            ts = pd.Timestamp(entry[0], unit="s", tz="UTC").tz_convert(None)
            low, high, open_, close, volume = entry[1:6]
            rows.append(
                {
                    "timestamp": ts,
                    "Open": float(open_),
                    "High": float(high),
                    "Low": float(low),
                    "Close": float(close),
                    "Adj Close": float(close),
                    "Volume": float(volume),
                }
            )

        current_start = current_end

    if not rows:
        return None

    frame = pd.DataFrame(rows)
    if frame.empty:
        return None

    frame = frame.drop_duplicates("timestamp").set_index("timestamp")
    frame = frame.sort_index()
    expected_cols = [c for c in FIELDS_ORDER if c in frame.columns]
    frame = frame[expected_cols]

    out = pd.concat({ticker: frame}, axis=1)
    if cache_expire is not None:
        _save_cache(key, out)
    return out


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
    cache_expire = cache_expire if cache_expire is not None else DEFAULT_CACHE_EXPIRY

    crypto_only = tickers and all(_is_crypto_symbol(t) for t in tickers)

    if use_alpaca_crypto() and crypto_only:
        log.info("Fetching crypto data via Alpaca for tickers: %s", tickers)
        try:
            return _get_crypto_data_alpaca(tickers, start, end, iv)
        except Exception as exc:
            log.error("Alpaca crypto data fetch failed: %s", exc)
            log.info("Falling back to Yahoo Finance for crypto data.")

    _quiet_yf_logs()

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
            alt = _download_history(t, start=start, end=end, interval=iv)
            if alt is not None and not alt.dropna(how="all").empty:
                log.info("Fetched %s via yfinance.Ticker.history fallback", t)
                _save_cache(f"{t}|history|{iv}|{start}|{end}", alt)
                return t, alt, False
            alt_chart = _download_chart(
                t,
                start=start,
                end=end,
                interval=iv,
                cache_expire=cache_expire,
            )
            if alt_chart is not None and not alt_chart.dropna(how="all").empty:
                log.info("Fetched %s via Yahoo chart API fallback", t)
                return t, alt_chart, False
            if crypto_only:
                alt_coinbase = _download_coinbase(
                    t,
                    start=start,
                    end=end,
                    interval=iv,
                    cache_expire=cache_expire,
                )
                if alt_coinbase is not None and not alt_coinbase.dropna(how="all").empty:
                    log.info("Fetched %s via Coinbase candles fallback", t)
                    return t, alt_coinbase, False
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
                alt = _download_history(t, start=start, end=end, interval=iv)
                if alt is None or alt.dropna(how="all").empty:
                    alt_chart = _download_chart(
                        t,
                        start=start,
                        end=end,
                        interval=iv,
                        cache_expire=cache_expire,
                    )
                    if alt_chart is None or alt_chart.dropna(how="all").empty:
                        if crypto_only:
                            alt_coinbase = _download_coinbase(
                                t,
                                start=start,
                                end=end,
                                interval=iv,
                                cache_expire=cache_expire,
                            )
                            if (
                                alt_coinbase is not None
                                and not alt_coinbase.dropna(how="all").empty
                            ):
                                frames.append(alt_coinbase)
                                continue
                        missing.append(t)
                        continue
                    frames.append(alt_chart)
                    continue
                frames.append(alt)
                continue
            frames.append(d1)
        except Exception:
            alt = _download_history(t, start=start, end=end, interval=iv)
            if alt is None or alt.dropna(how="all").empty:
                alt_chart = _download_chart(
                    t,
                    start=start,
                    end=end,
                    interval=iv,
                    cache_expire=cache_expire,
                )
                if alt_chart is None or alt_chart.dropna(how="all").empty:
                    if crypto_only:
                        alt_coinbase = _download_coinbase(
                            t,
                            start=start,
                            end=end,
                            interval=iv,
                            cache_expire=cache_expire,
                        )
                        if (
                            alt_coinbase is not None
                            and not alt_coinbase.dropna(how="all").empty
                        ):
                            frames.append(alt_coinbase)
                            continue
                    missing.append(t)
                    continue
                frames.append(alt_chart)
                continue
            frames.append(alt)

    if frames:
        out = pd.concat(frames, axis=1).sort_index()
        if missing:
            log.warning("%d Failed downloads:\n%s", len(missing), missing)
        return out

    if missing:
        raise RuntimeError(f"No data returned for {missing}.")
    raise RuntimeError(f"Failed to download data: {last_err}")



