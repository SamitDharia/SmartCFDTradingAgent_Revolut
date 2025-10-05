import io
import json
import logging
from smartcfd.config import load_config, AppConfig
from smartcfd.logging_setup import setup_logging, JsonFormatter

def test_load_config_defaults(monkeypatch):
    for k in [
        "TIMEZONE","ALPACA_ENV","API_TIMEOUT_SECONDS","NETWORK_MAX_BACKOFF_SECONDS",
        "ON_RECONNECT_RECONCILE","RUN_CONTAINER_SMOKE_TEST","ORDER_CLIENT_ID_PREFIX","OFFLINE_BEHAVIOR"
    ]:
        monkeypatch.delenv(k, raising=False)
    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.timezone == "Europe/Dublin"
    assert cfg.alpaca_env == "paper"
    assert cfg.api_timeout_seconds == 10.0
    assert cfg.network_max_backoff_seconds == 60
    assert cfg.on_reconnect_reconcile is True
    assert cfg.run_container_smoke_test is True
    assert cfg.order_client_id_prefix == "SCFD"
    assert cfg.offline_behavior == "halt"

def test_load_config_env(monkeypatch):
    monkeypatch.setenv("TIMEZONE", "UTC")
    monkeypatch.setenv("ALPACA_ENV", "paper")
    monkeypatch.setenv("API_TIMEOUT_SECONDS", "5.5")
    monkeypatch.setenv("NETWORK_MAX_BACKOFF_SECONDS", "120")
    monkeypatch.setenv("ON_RECONNECT_RECONCILE", "false")
    monkeypatch.setenv("RUN_CONTAINER_SMOKE_TEST", "0")
    monkeypatch.setenv("ORDER_CLIENT_ID_PREFIX", "X")
    monkeypatch.setenv("OFFLINE_BEHAVIOR", "continue")
    cfg = load_config()
    assert cfg.timezone == "UTC"
    assert cfg.api_timeout_seconds == 5.5
    assert cfg.network_max_backoff_seconds == 120
    assert cfg.on_reconnect_reconcile is False
    assert cfg.run_container_smoke_test is False
    assert cfg.order_client_id_prefix == "X"
    assert cfg.offline_behavior == "continue"

def test_logging_json_format():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonFormatter())

    logger = logging.getLogger("json-test")
    logger.handlers = []
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False

    logger.info("hi", extra={"extra": {"a": 1}})

    out = stream.getvalue().strip()
    data = json.loads(out)
    assert data["msg"] == "hi"
    assert data["level"] == "INFO"
    assert data["logger"] == "json-test"
    assert data["a"] == 1
