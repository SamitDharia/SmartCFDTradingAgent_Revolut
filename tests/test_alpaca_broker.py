import types, sys


def test_alpaca_payload(monkeypatch):
    calls = {}

    class FakeREST:
        def __init__(self, key, secret, base_url=None):
            pass

        def submit_order(self, **kwargs):
            calls.update(kwargs)
            return types.SimpleNamespace(id="1")

    fake_mod = types.SimpleNamespace(REST=FakeREST)
    monkeypatch.setitem(sys.modules, "alpaca_trade_api", fake_mod)

    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_API_SECRET", "s")
    monkeypatch.setenv("ALPACA_PAPER", "true")
    monkeypatch.setenv("ALLOW_FRACTIONAL", "true")

    from SmartCFDTradingAgent.brokers.alpaca import AlpacaBroker

    broker = AlpacaBroker()
    broker.submit_order("AAPL", "buy", 1.5, sl=9, tp=12, dry_run=False)

    assert calls["symbol"] == "AAPL"
    assert str(calls["qty"]) == "1.5"
    assert calls["order_class"] == "bracket"
    assert calls["take_profit"]["limit_price"] == 12
    assert calls["stop_loss"]["stop_price"] == 9
