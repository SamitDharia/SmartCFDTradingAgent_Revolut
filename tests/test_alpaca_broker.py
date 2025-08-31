import sys
import types

# stub requests to avoid optional dependency during import
sys.modules.setdefault("requests", types.SimpleNamespace(post=lambda *a, **kw: None))
sys.modules.setdefault("dotenv", types.SimpleNamespace(load_dotenv=lambda: None))

from SmartCFDTradingAgent.brokers.alpaca import AlpacaBroker
import SmartCFDTradingAgent.brokers.alpaca as alpaca


class DummyAPI:
    def __init__(self, *args, **kwargs):
        self.orders = []

    def get_account(self):
        return types.SimpleNamespace(equity="1000")

    def submit_order(self, **kwargs):
        self.orders.append(kwargs)
        return types.SimpleNamespace(id="1", status="accepted")


def test_alpaca_broker_submit_and_equity(monkeypatch):
    dummy = DummyAPI()
    monkeypatch.setattr(
        alpaca, "tradeapi", types.SimpleNamespace(REST=lambda *a, **kw: dummy)
    )
    broker = AlpacaBroker()
    assert isinstance(broker, AlpacaBroker)
    assert broker.get_equity() == 1000.0
    res = broker.submit_order("AAPL", "buy", 1)
    assert res["symbol"] == "AAPL"
    assert dummy.orders[0]["symbol"] == "AAPL"


class DummyAPIError:
    def __init__(self, *args, **kwargs):
        pass

    def get_account(self):  # pragma: no cover - exercised in test
        raise RuntimeError("boom")

    def submit_order(self, **kwargs):  # pragma: no cover - unused
        return types.SimpleNamespace(id="1", status="accepted")


def test_alpaca_broker_get_equity_error(monkeypatch, caplog):
    dummy = DummyAPIError()
    monkeypatch.setattr(
        alpaca, "tradeapi", types.SimpleNamespace(REST=lambda *a, **kw: dummy)
    )
    broker = AlpacaBroker()
    with caplog.at_level("ERROR", logger="alpaca-broker"):
        assert broker.get_equity() is None
    assert "Account retrieval failed" in caplog.text
