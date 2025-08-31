import json
from pathlib import Path

from SmartCFDTradingAgent.brokers.manual import ManualBroker


def test_manual_broker_ticket_creation(tmp_path, monkeypatch):
    msgs = []
    monkeypatch.setattr(
        "SmartCFDTradingAgent.brokers.manual.tg_send",
        lambda text: msgs.append(text),
    )
    broker = ManualBroker(ticket_dir=tmp_path)
    ticket = broker.submit_order("AAPL", "buy", 1, entry=10, sl=9, tp=12)
    assert "AAPL" in msgs[0]
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["symbol"] == "AAPL"
    assert ticket["symbol"] == "AAPL"
