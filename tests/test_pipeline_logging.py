import csv
import sqlite3
import sys
import types


class FakeSeries(list):
    def dropna(self):
        return self

    def tail(self, n):
        return FakeSeries(self[-n:])

    @property
    def iloc(self):
        return self


sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda *a, **k: None))
sys.modules.setdefault(
    "SmartCFDTradingAgent.utils.market_time",
    types.SimpleNamespace(market_open=lambda *a, **k: True),
)
sys.modules.setdefault(
    "requests",
    types.SimpleNamespace(post=lambda *a, **k: types.SimpleNamespace(status_code=200, json=lambda: {}, text="")),
)
sys.modules.setdefault(
    "SmartCFDTradingAgent.rank_assets",
    types.SimpleNamespace(top_n=lambda watch, size: watch),
)
sys.modules.setdefault(
    "SmartCFDTradingAgent.data_loader",
    types.SimpleNamespace(get_price_data=lambda *a, **k: {}),
)
sys.modules.setdefault(
    "SmartCFDTradingAgent.signals",
    types.SimpleNamespace(generate_signals=lambda *a, **k: {}),
)
sys.modules.setdefault(
    "SmartCFDTradingAgent.backtester",
    types.SimpleNamespace(backtest=lambda *a, **k: ({"cum_return": FakeSeries([1, 1.1])}, {"sharpe":1,"max_drawdown":0.1,"win_rate":0.5}, None)),
)
sys.modules.setdefault(
    "SmartCFDTradingAgent.position",
    types.SimpleNamespace(qty_from_atr=lambda *a, **k: 1),
)
sys.modules.setdefault(
    "SmartCFDTradingAgent.indicators",
    types.SimpleNamespace(
        adx=lambda *a, **k: FakeSeries([30]),
        atr=lambda *a, **k: FakeSeries([1, 1]),
    ),
)

from SmartCFDTradingAgent import pipeline
from SmartCFDTradingAgent.utils import trade_logger


def test_dry_run_cycle_logging_and_summary(monkeypatch, tmp_path, caplog):
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
        data = {}
        for t in tickers:
            data[t] = {
                "High": FakeSeries([10] * 5),
                "Low": FakeSeries([8] * 5),
                "Close": FakeSeries([9] * 5),
            }
        return data

    monkeypatch.setattr(pipeline, "get_price_data", fake_price)
    monkeypatch.setattr(pipeline, "generate_signals", lambda price, **k: {list(price.keys())[0]: "Buy"})
    monkeypatch.setattr(pipeline, "qty_from_atr", lambda atr, equity, risk: 1)
    monkeypatch.setattr(pipeline, "_adx", lambda *a, **k: FakeSeries([30]))

    def fake_backtest(price, base_sig, **kwargs):
        pnl = {"cum_return": FakeSeries([1, 1.1])}
        return pnl, {"sharpe": 1, "max_drawdown": 0.1, "win_rate": 0.5}, None

    monkeypatch.setattr(pipeline, "backtest", fake_backtest)

    with caplog.at_level("INFO"):
        pipeline.run_cycle(watch=["AAA"], size=1, grace=0, risk=0.01, qty=1000, force=True)

    assert any(msg.startswith("Summary:") for msg in sent)
    assert "Summary:" in caplog.text

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


def test_show_decisions_logs(monkeypatch, caplog):
    monkeypatch.setattr(pipeline, "read_last_decisions", lambda n: [])
    monkeypatch.setattr(pipeline, "format_decisions", lambda rows: "No decisions")
    monkeypatch.setattr(pipeline, "safe_send", lambda msg: None)
    monkeypatch.setattr(sys, "argv", ["prog", "--show-decisions", "1"])
    with caplog.at_level("INFO"):
        pipeline.main()
    assert "No decisions" in caplog.text
