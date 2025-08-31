import types

from SmartCFDTradingAgent.brokers import get_broker, AlpacaBroker
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
    broker = get_broker("alpaca")
    assert isinstance(broker, AlpacaBroker)
    assert broker.get_equity() == 1000.0
    res = broker.submit_order("AAPL", "buy", 1)
    assert res["symbol"] == "AAPL"
    assert dummy.orders[0]["symbol"] == "AAPL"
