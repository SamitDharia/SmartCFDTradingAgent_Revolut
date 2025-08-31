import importlib
import SmartCFDTradingAgent.utils.telegram as telegram


def test_telegram_noop(monkeypatch, caplog):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    importlib.reload(telegram)
    with caplog.at_level("WARNING"):
        ok = telegram.send("hello")
    assert ok is False
    assert "skipping" in caplog.text.lower()
