from __future__ import annotations
import SmartCFDTradingAgent.utils.no_ssl  # must be first

import argparse
import datetime as dt
from typing import Dict, Iterable, List

import pandas as pd

from SmartCFDTradingAgent.data_loader import get_price_data


def _sharpe(close: pd.Series, lb: int) -> float:
    r = close.pct_change().dropna().tail(lb)
    if len(r) < 2:
        return 0.0
    return (r.mean() / (r.std() or 1e-9)) * (252 ** 0.5)


def _momentum(close: pd.Series, lb: int) -> float:
    if len(close) <= lb:
        return 0.0
    start = close.iloc[-lb]
    end = close.iloc[-1]
    return (end / start) - 1.0


def _avg_volume(volume: pd.Series, lb: int) -> float:
    return volume.tail(lb).mean() if not volume.empty else 0.0


def _volatility(close: pd.Series, lb: int) -> float:
    r = close.pct_change().dropna().tail(lb)
    return r.std() * (252 ** 0.5) if not r.empty else 0.0


def top_n(
    tickers: Iterable[str],
    n: int,
    *,
    lookbacks: Dict[str, int] | None = None,
    weights: Dict[str, float] | None = None,
) -> List[str]:
    """Rank tickers by composite score and return the top ``n``.

    Parameters
    ----------
    tickers:
        Iterable of ticker symbols.
    n:
        Number of tickers to return.
    lookbacks:
        Optional dict specifying lookback windows for metrics.
        Keys: ``sharpe``, ``momentum``, ``volume``, ``volatility``.
    weights:
        Optional dict specifying weights for metrics. Same keys as above.
    """

    tickers = list(dict.fromkeys(tickers))
    if not tickers:
        return []

    lookbacks = {
        "sharpe": 30,
        "momentum": 252,
        "volume": 30,
        "volatility": 30,
        **(lookbacks or {}),
    }

    weights = {
        "sharpe": 0.4,
        "momentum": 0.3,
        "volume": 0.2,
        "volatility": -0.1,
        **(weights or {}),
    }

    end = dt.date.today().isoformat()
    max_lb = max(lookbacks.values())
    start = (dt.date.today() - dt.timedelta(days=max_lb + 5)).isoformat()

    try:
        df = get_price_data(tickers, start, end, interval="1d")
    except Exception as e:
        print(
            f"[rank_assets] daily ranking failed ({e}); returning unranked first {n}."
        )
        return tickers[: min(n, len(tickers))]

    metrics = {k: {} for k in lookbacks}

    for t in tickers:
        try:
            close = df[t]["Close"].dropna()
            volume = df[t].get("Volume", pd.Series(dtype=float)).dropna()

            metrics["sharpe"][t] = _sharpe(close, lookbacks["sharpe"])
            metrics["momentum"][t] = _momentum(close, lookbacks["momentum"])
            metrics["volume"][t] = _avg_volume(volume, lookbacks["volume"])
            metrics["volatility"][t] = _volatility(close, lookbacks["volatility"])
        except Exception:
            for m in metrics:
                metrics[m][t] = float("nan")

    scores: Dict[str, float] = {t: 0.0 for t in tickers}
    for name, vals in metrics.items():
        series = pd.Series(vals)
        if series.isna().all():
            continue
        z = (series - series.mean()) / (series.std() or 1e-9)
        w = weights.get(name, 0.0)
        for t in tickers:
            scores[t] += z.get(t, 0.0) * w

    ranked = sorted(tickers, key=lambda t: scores.get(t, -1e9), reverse=True)
    return ranked[: min(n, len(ranked))]


def _parse_weights(s: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    if not s:
        return out
    for part in s.split(","):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        try:
            out[k.strip()] = float(v)
        except ValueError:
            pass
    return out


def main(argv: Iterable[str] | None = None) -> None:
    ap = argparse.ArgumentParser("rank_assets")
    ap.add_argument("tickers", nargs="*", help="Tickers to rank")
    ap.add_argument("-n", "--top", type=int, default=5, help="Number of tickers")
    ap.add_argument("--sharpe-lookback", type=int, default=30)
    ap.add_argument("--momentum-lookback", type=int, default=252)
    ap.add_argument("--volume-lookback", type=int, default=30)
    ap.add_argument("--volatility-lookback", type=int, default=30)
    ap.add_argument(
        "--weights",
        default="",
        help="Comma-separated weights, e.g. sharpe=0.4,momentum=0.3",
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

    lookbacks = {
        "sharpe": cfg.get("sharpe_lookback", args.sharpe_lookback),
        "momentum": cfg.get("momentum_lookback", args.momentum_lookback),
        "volume": cfg.get("volume_lookback", args.volume_lookback),
        "volatility": cfg.get("volatility_lookback", args.volatility_lookback),
    }

    weights = cfg.get("weights", {})
    cli_weights = _parse_weights(args.weights)
    weights.update(cli_weights)

    ranked = top_n(tickers, topn, lookbacks=lookbacks, weights=weights)
    print(ranked)


if __name__ == "__main__":
    main()

