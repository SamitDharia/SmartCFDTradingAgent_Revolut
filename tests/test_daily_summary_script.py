import importlib.util
import sys
import types
from pathlib import Path

import pytest


def _load_daily_summary(monkeypatch):
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "daily_summary.py"
    stub = types.SimpleNamespace(send=lambda msg: None)
    monkeypatch.setitem(sys.modules, "SmartCFDTradingAgent.utils.telegram", stub)
    spec = importlib.util.spec_from_file_location("daily_summary", script_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, stub


def test_daily_summary_sends_message(monkeypatch):
    ds, stub = _load_daily_summary(monkeypatch)
    monkeypatch.setattr(ds, "aggregate_trade_stats", lambda: {"wins": 2, "losses": 1, "open": 3})
    sent = {}

    def fake_send(msg: str) -> None:
        sent["msg"] = msg

    monkeypatch.setattr(stub, "send", fake_send)
    ds.main()
    assert "Wins: 2" in sent["msg"]
    assert "Losses: 1" in sent["msg"]
    assert "Open trades: 3" in sent["msg"]
