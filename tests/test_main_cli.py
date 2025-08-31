import datetime as dt
import sys
import types
import importlib
import logging

# Provide lightweight stubs for modules imported by the CLI
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
    types.SimpleNamespace(backtest=lambda *a, **k: None),
)


def test_cli_argument_parsing(monkeypatch):
    import SmartCFDTradingAgent.__main__ as main

    captured = {}

    def fake_get_price_data(tickers, start, end, interval):
        captured["tickers"] = tickers
        captured["start"] = start
        captured["end"] = end
        captured["interval"] = interval
        return {}

    monkeypatch.setattr(main, "get_price_data", fake_get_price_data)

    monkeypatch.setattr(sys, "argv", [
        "prog",
        "--tickers",
        "AAA",
        "BBB",
        "--start",
        "2024-01-01",
        "--end",
        "2024-01-02",
        "--interval",
        "1h",
    ])

    main.cli()

    assert captured == {
        "tickers": ["AAA", "BBB"],
        "start": "2024-01-01",
        "end": "2024-01-02",
        "interval": "1h",
    }


def test_cli_creates_log_file(monkeypatch, tmp_path):
    log_root = tmp_path / "pkg"
    log_root.mkdir()

    logger_obj = logging.getLogger("SmartCFD")
    for h in list(logger_obj.handlers):
        logger_obj.removeHandler(h)

    sys.modules.pop("SmartCFDTradingAgent.__main__", None)
    sys.modules.pop("SmartCFDTradingAgent.utils.logger", None)

    logger = importlib.import_module("SmartCFDTradingAgent.utils.logger")
    monkeypatch.setattr(logger, "__file__", str(log_root / "utils" / "logger.py"))
    sys.modules["SmartCFDTradingAgent.utils.logger"] = logger

    main = importlib.import_module("SmartCFDTradingAgent.__main__")

    monkeypatch.setattr(sys, "argv", [
        "prog",
        "--tickers",
        "AAA",
        "--start",
        "2024-01-01",
        "--end",
        "2024-01-02",
    ])

    main.cli()

    log_file = log_root / "logs" / f"{dt.datetime.now():%Y%m%d}.log"
    assert log_file.exists()
