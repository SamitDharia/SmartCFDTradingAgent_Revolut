import csv
import sqlite3
import pandas as pd

from SmartCFDTradingAgent import pipeline
from SmartCFDTradingAgent.utils import trade_logger


def test_dry_run_cycle_logging_and_summary(monkeypatch, tmp_path):
    sent = []
    monkeypatch.setattr(pipeline, "safe_send", lambda msg: sent.append(msg))
    monkeypatch.setattr(pipeline, "market_open", lambda: True)
    monkeypatch.setattr(pipeline, "STORE", tmp_path)
    monkeypatch.setattr(pipeline, "COOL_PATH", tmp_path / "last_signals.json")

    monkeypatch.setattr(trade_logger, "STORE", tmp_path, raising=False)
    monkeypatch.setattr(trade_logger, "CSV_PATH", tmp_path / "trade_log.csv", raising=False)
    monkeypatch.setattr(trade_logger, "DB_PATH", tmp_path / "trade_log.sqlite", raising=False)

    monkeypatch.setattr(pipeline, "top_n", lambda watch, size: watch)

    def fake_price(tickers, start, end, interval="1d"):
        idx = pd.date_range("2020-01-01", periods=5, freq="D")
        data = {}
        for t in tickers:
            data[(t, "High")] = pd.Series([10]*5, index=idx)
            data[(t, "Low")] = pd.Series([8]*5, index=idx)
            data[(t, "Close")] = pd.Series([9]*5, index=idx)
        return pd.DataFrame(data)

    monkeypatch.setattr(pipeline, "get_price_data", fake_price)
    monkeypatch.setattr(pipeline, "generate_signals", lambda price, **k: {list(price.columns.levels[0])[0]: "Buy"})
    monkeypatch.setattr(pipeline, "qty_from_atr", lambda atr, equity, risk: 1)

    def fake_backtest(price, base_sig, **kwargs):
        return pd.DataFrame({"cum_return": [1, 1.1]}), {"sharpe": 1, "max_drawdown": 0.1, "win_rate": 0.5}, None

    monkeypatch.setattr(pipeline, "backtest", fake_backtest)

    pipeline.run_cycle(watch=["AAA"], size=1, grace=0, risk=0.01, equity=1000, force=True)

    assert any(msg.startswith("Summary:") for msg in sent)

    decision_log = tmp_path / "decision_log.csv"
    assert decision_log.exists()

    trade_logger.log_trade({
        "ticker": "AAA",
        "side": "Buy",
        "entry": 9.0,
        "sl": 8.0,
        "tp": 10.0,
        "exit": 9.5,
        "exit_reason": "test",
        "atr": 1.0,
        "r_multiple": 1.5,
        "fees": 0.1,
        "broker": "demo",
        "order_id": "1",
    })

    csv_path = tmp_path / "trade_log.csv"
    assert csv_path.exists()
    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["ticker"] == "AAA"

    db_path = tmp_path / "trade_log.sqlite"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT ticker FROM trades")
    assert cur.fetchone()[0] == "AAA"
    conn.close()
