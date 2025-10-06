import pytest

pd = pytest.importorskip("pandas")

from SmartCFDTradingAgent import pipeline


def test_run_cycle_uses_broker_equity(monkeypatch, tmp_path):
    recorded = {}

    def fake_qty_from_atr(atr, equity, risk):
        recorded["equity"] = equity
        return 1

    monkeypatch.setattr(pipeline, "qty_from_atr", fake_qty_from_atr)
    monkeypatch.setattr(pipeline, "safe_send", lambda msg: None)
    monkeypatch.setattr(pipeline, "market_open", lambda: True)
    monkeypatch.setattr(pipeline, "STORE", tmp_path)
    monkeypatch.setattr(pipeline, "COOL_PATH", tmp_path / "last_signals.json")
    monkeypatch.setattr(pipeline, "top_n", lambda watch, size: watch)

    def fake_price(tickers, start, end, interval="1d"):
        idx = pd.date_range("2020-01-01", periods=20, freq="D")
        data = {}
        for t in tickers:
            data[(t, "High")] = pd.Series(range(20), index=idx) + 10
            data[(t, "Low")] = pd.Series(range(20), index=idx) + 8
            data[(t, "Close")] = pd.Series(range(20), index=idx) + 9
        return pd.DataFrame(data)

    monkeypatch.setattr(pipeline, "get_price_data", fake_price)
    monkeypatch.setattr(
        pipeline,
        "generate_signals",
        lambda price, **k: {list(price.columns.levels[0])[0]: "Buy"},
    )
    monkeypatch.setattr(
        pipeline,
        "backtest",
        lambda price, sig_map, **kwargs: (
            pd.DataFrame({"cum_return": [1.0]}),
            {"sharpe": 0, "max_drawdown": 0, "win_rate": 0},
            None,
        ),
    )

    class DummyBroker:
        def __init__(self, equity):
            self._equity = equity

        def get_equity(self):
            return self._equity

        def submit_order(self, *args, **kwargs):
            pass

    broker = DummyBroker(5000)

    pipeline.run_cycle(
        watch=["AAA"],
        size=1,
        grace=0,
        risk=0.01,
        qty=1000,
        broker=broker,
        force=True,
        max_trade_risk=0.01,
    )

    assert recorded["equity"] == 5000


def test_run_cycle_handles_none_equity(monkeypatch, tmp_path):
    recorded = {}

    def fake_qty_from_atr(atr, equity, risk):
        recorded["equity"] = equity
        return 1

    monkeypatch.setattr(pipeline, "qty_from_atr", fake_qty_from_atr)
    monkeypatch.setattr(pipeline, "safe_send", lambda msg: None)
    monkeypatch.setattr(pipeline, "market_open", lambda: True)
    monkeypatch.setattr(pipeline, "STORE", tmp_path)
    monkeypatch.setattr(pipeline, "COOL_PATH", tmp_path / "last_signals.json")
    monkeypatch.setattr(pipeline, "top_n", lambda watch, size: watch)

    def fake_price(tickers, start, end, interval="1d"):
        idx = pd.date_range("2020-01-01", periods=20, freq="D")
        data = {}
        for t in tickers:
            data[(t, "High")] = pd.Series(range(20), index=idx) + 10
            data[(t, "Low")] = pd.Series(range(20), index=idx) + 8
            data[(t, "Close")] = pd.Series(range(20), index=idx) + 9
        return pd.DataFrame(data)

    monkeypatch.setattr(pipeline, "get_price_data", fake_price)
    monkeypatch.setattr(
        pipeline,
        "generate_signals",
        lambda price, **k: {list(price.columns.levels[0])[0]: "Buy"},
    )
    monkeypatch.setattr(
        pipeline,
        "backtest",
        lambda price, sig_map, **kwargs: (
            pd.DataFrame({"cum_return": [1.0]}),
            {"sharpe": 0, "max_drawdown": 0, "win_rate": 0},
            None,
        ),
    )

    class DummyBrokerNone:
        def get_equity(self):
            return None

        def submit_order(self, *args, **kwargs):
            pass

    broker = DummyBrokerNone()

    pipeline.run_cycle(
        watch=["AAA"],
        size=1,
        grace=0,
        risk=0.01,
        qty=1000,
        broker=broker,
        force=True,
        max_trade_risk=0.01,
    )

    assert recorded["equity"] == 1000
