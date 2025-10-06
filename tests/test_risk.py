import pytest
from unittest.mock import MagicMock
import requests_mock

from smartcfd.risk import RiskManager, Account, Position
from smartcfd.config import RiskConfig
from smartcfd.alpaca_client import get_alpaca_client

@pytest.fixture
def risk_config():
    """Provides a default RiskConfig for tests."""
    return RiskConfig(
        max_daily_drawdown_percent=-5.0,
        max_position_size=1000.0,
        max_total_exposure=10000.0
    )

@pytest.fixture
def alpaca_client():
    """Provides an AlpacaClient instance for tests."""
    return get_alpaca_client("http://mock.alpaca.api")

@pytest.fixture
def risk_manager(alpaca_client, risk_config):
    """Provides a RiskManager instance for tests."""
    return RiskManager(client=alpaca_client, config=risk_config)

def test_check_for_halt_no_drawdown(risk_manager, requests_mock):
    """
    Verify that trading is NOT halted when drawdown is within limits.
    """
    account_payload = {
        "equity": "100000",
        "last_equity": "100000",
        "buying_power": "200000"
    }
    requests_mock.get("http://mock.alpaca.api/v2/account", json=account_payload)
    
    assert not risk_manager.check_for_halt()
    assert not risk_manager.is_halted

def test_check_for_halt_exceeds_drawdown(risk_manager, requests_mock):
    """
    Verify that trading IS halted when the max daily drawdown is exceeded.
    """
    # 6% drawdown (94000 equity from 100000) exceeds the -5% limit
    account_payload = {
        "equity": "94000",
        "last_equity": "100000",
        "buying_power": "200000"
    }
    requests_mock.get("http://mock.alpaca.api/v2/account", json=account_payload)
    
    assert risk_manager.check_for_halt()
    assert risk_manager.is_halted

def test_check_for_halt_api_failure(risk_manager, requests_mock):
    """
    Verify that trading is halted as a fail-safe if account info cannot be fetched.
    """
    requests_mock.get("http://mock.alpaca.api/v2/account", status_code=500)
    
    assert risk_manager.check_for_halt()
    assert risk_manager.is_halted

def test_filter_actions_no_halt(risk_manager, requests_mock):
    """
    Verify that valid actions are approved when not halted.
    """
    requests_mock.get("http://mock.alpaca.api/v2/positions", json=[]) # No existing positions
    
    actions = [
        {"action": "buy", "order_details": {"symbol": "AAPL", "qty": "5", "side": "buy", "type": "market", "time_in_force": "day"}}
    ]
    
    approved = risk_manager.filter_actions(actions)
    assert len(approved) == 1
    assert approved[0]["order_details"]["symbol"] == "AAPL"

def test_filter_actions_when_halted(risk_manager):
    """
    Verify that no actions are approved when trading is halted.
    """
    risk_manager.is_halted = True
    actions = [
        {"action": "buy", "order_details": {"symbol": "AAPL", "qty": "5", "side": "buy", "type": "market", "time_in_force": "day"}}
    ]
    
    approved = risk_manager.filter_actions(actions)
    assert len(approved) == 0

def test_filter_actions_exceeds_max_position_size(risk_manager, requests_mock):
    """
    Verify that an action is rejected if it exceeds the max position size.
    max_position_size is 1000.0. Order notional is 10 * 150 = 1500.
    """
    requests_mock.get("http://mock.alpaca.api/v2/positions", json=[])
    
    actions = [
        {"action": "buy", "order_details": {"symbol": "GOOG", "qty": "10", "side": "buy", "type": "market", "time_in_force": "day"}}
    ]
    
    approved = risk_manager.filter_actions(actions)
    assert len(approved) == 0

def test_filter_actions_exceeds_max_total_exposure(risk_manager, requests_mock):
    """
    Verify that an action is rejected if it causes total exposure to be exceeded.
    max_total_exposure is 10000.0. Existing position is 9500. New order is 6 * 150 = 900.
    Total would be 10400.
    """
    existing_positions = [
        {"symbol": "MSFT", "qty": "50", "market_value": "9500", "unrealized_pl": "100"}
    ]
    requests_mock.get("http://mock.alpaca.api/v2/positions", json=existing_positions)
    
    actions = [
        {"action": "buy", "order_details": {"symbol": "TSLA", "qty": "6", "side": "buy", "type": "market", "time_in_force": "day"}}
    ]
    
    approved = risk_manager.filter_actions(actions)
    assert len(approved) == 0

def test_filter_actions_sell_action_is_not_filtered(risk_manager, requests_mock):
    """
    Verify that 'sell' actions are not subject to the same size checks and are passed through.
    """
    requests_mock.get("http://mock.alpaca.api/v2/positions", json=[])
    
    actions = [
        {"action": "sell", "order_details": {"symbol": "AAPL", "qty": "100", "side": "sell", "type": "market", "time_in_force": "day"}}
    ]
    
    approved = risk_manager.filter_actions(actions)
    assert len(approved) == 1
    assert approved[0]["action"] == "sell"
