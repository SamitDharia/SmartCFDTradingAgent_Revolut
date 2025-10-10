import sqlite3
import pandas as pd
from unittest.mock import MagicMock

from smartcfd.trader import Trader
from smartcfd.config import AppConfig, RiskConfig, RegimeConfig
from smartcfd.db import init_schema
from smartcfd.portfolio import PortfolioManager
from smartcfd.risk import RiskManager


def _make_trader_with_mocks():
    app_cfg = AppConfig(watch_list="BTC/USD", trade_interval="15m")
    risk_cfg = RiskConfig()
    regime_cfg = RegimeConfig()
    broker = MagicMock()

    # In-memory DB for trade groups
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)

    portfolio_manager = PortfolioManager(broker)
    risk_manager = RiskManager(portfolio_manager, risk_cfg, broker)

    trader = Trader(
        app_config=app_cfg,
        risk_config=risk_cfg,
        regime_config=regime_cfg,
        broker=broker,
        db_conn=conn,
        portfolio_manager=portfolio_manager,
        risk_manager=risk_manager,
    )
    return trader, broker, risk_manager


def test_initiate_trade_submits_entry_order():
    trader, broker, risk_manager = _make_trader_with_mocks()
    # Risk returns > 0 qty and basic order dict
    risk_manager.calculate_order_qty = MagicMock(return_value=(0.02, 50000.0))
    risk_manager.generate_entry_order = MagicMock(return_value={
        "symbol": "BTC/USD",
        "qty": "0.02",
        "side": "buy",
        "type": "market",
        "time_in_force": "gtc",
    })
    # Broker returns an object with id attribute
    broker.submit_order.return_value = MagicMock(id="ord_1")

    trade_details = {"symbol": "BTC/USD", "side": "buy"}
    df = pd.DataFrame({"close": [50000, 50010]})

    trader.initiate_trade(trade_details, df)
    assert broker.submit_order.called


def test_initiate_trade_zero_qty_no_order():
    trader, broker, risk_manager = _make_trader_with_mocks()
    risk_manager.calculate_order_qty = MagicMock(return_value=(0.0, 50000.0))
    trade_details = {"symbol": "BTC/USD", "side": "buy"}
    trader.initiate_trade(trade_details, pd.DataFrame({"close": [50000]}))
    assert not broker.submit_order.called

