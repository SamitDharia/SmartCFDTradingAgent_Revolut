from __future__ import annotations

import argparse
import datetime as dt
from typing import Iterable, List

import pandas as pd

from SmartCFDTradingAgent.utils.logger import get_logger

log = get_logger()


def get_price_data(*args, **kwargs):
    """
    Placeholder for the old get_price_data function.
    This can be removed once all dependencies are updated.
    """
    log.warning("get_price_data is deprecated and should be replaced.")
    return pd.DataFrame()


def top_n(
    tickers: Iterable[str],
    n: int,
    *,
    lookback: int = 60,
    min_dollar_volume: float = 0.0,
) -> List[str]:
    """Rank tickers by return-based score and return the top ``n``.

    The score is ``mean(returns) / std(returns)`` over the last ``lookback`` bars.
    Tickers whose median dollar volume over the same window is below
    ``min_dollar_volume`` are excluded before ranking.
    """

    tickers = list(dict.fromkeys(tickers))
    if not tickers:
        return []

    end = dt.date.today().isoformat()
    start = (dt.date.today() - dt.timedelta(days=lookback + 5)).isoformat()

    try:
        df = get_price_data(tickers, start, end, interval="1d")
    except Exception as e:
        log.warning(
            "[rank_assets] daily ranking failed (%s); returning unranked first %s.",
            e,
            n,
        )
        return tickers[: min(n, len(tickers))]

    scores: dict[str, float] = {}
    for t in tickers:
        try:
            close = df[t]["Close"].dropna()
            volume = df[t].get("Volume", pd.Series(dtype=float)).dropna()

            ret = close.pct_change().dropna().tail(lookback)
            if ret.empty:
                continue

            med_dollar_vol = (close.tail(lookback) * volume.tail(lookback)).median()
            if pd.isna(med_dollar_vol) or med_dollar_vol < min_dollar_volume:
                continue

            scores[t] = ret.mean() / (ret.std() or 1e-9)
        except Exception:
            continue

    ranked = sorted(scores, key=lambda t: scores[t], reverse=True)
    return ranked[: min(n, len(ranked))]


def main(argv: Iterable[str] | None = None) -> None:
    ap = argparse.ArgumentParser("rank_assets")
    ap.add_argument("tickers", nargs="*", help="Tickers to rank")
    ap.add_argument("-n", "--top", type=int, default=5, help="Number of tickers")
    ap.add_argument("--lookback", type=int, default=60, help="Lookback window in bars")
    ap.add_argument(
        "--min-dollar-volume",
        type=float,
        default=0.0,
        dest="min_dollar_volume",
        help="Minimum median dollar volume over lookback window",
    )
    ap.add_argument("--config", help="Path to config file")
    ap.add_argument("--profile", help="Profile name inside config")

    args = ap.parse_args(list(argv) if argv is not None else None)

    cfg = {}
    if args.config:
        from SmartCFDTradingAgent.pipeline import load_profile_config

        cfg = load_profile_config(args.config, args.profile or "default")

    tickers = args.tickers or cfg.get("tickers", [])
    topn = args.top if args.top != ap.get_default("top") else cfg.get("top", args.top)
    lookback = cfg.get("lookback", args.lookback)
    min_dollar_volume = cfg.get("min_dollar_volume", args.min_dollar_volume)

    ranked = top_n(
        tickers,
        topn,
        lookback=lookback,
        min_dollar_volume=min_dollar_volume,
    )
    log.info("%s", ranked)


if __name__ == "__main__":
    main()
