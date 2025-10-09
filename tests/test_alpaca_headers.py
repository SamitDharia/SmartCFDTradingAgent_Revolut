import os
from smartcfd.alpaca_helpers import build_headers_from_env, build_api_base

def test_build_api_base():
    assert build_api_base("paper").endswith("paper-api.alpaca.markets")
    assert build_api_base("live").endswith("api.alpaca.markets")

def test_headers_present(monkeypatch):
    monkeypatch.setenv("APCA_API_KEY_ID", "key")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "secret")
    h = build_headers_from_env()
    assert h.get("APCA-API-KEY-ID") == "key"
    assert h.get("APCA-API-SECRET-KEY") == "secret"

def test_headers_absent(monkeypatch):
    for k in ("APCA_API_KEY_ID","APCA_API_SECRET_KEY","ALPACA_KEY_ID","ALPACA_SECRET_KEY"):
        monkeypatch.delenv(k, raising=False)
    h = build_headers_from_env()
    assert h == {}
