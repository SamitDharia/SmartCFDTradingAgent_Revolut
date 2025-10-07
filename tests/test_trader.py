import pytest
from unittest.mock import MagicMock

from smartcfd.trader import Trader
from smartcfd.config import AppConfig

@pytest.fixture
def mock_strategy():
    """Creates a mock strategy."""
    strategy = MagicMock()
    strategy.evaluate.return_value = (
        [
            {"action": "log", "message": "Holding position."},
            {"action": "buy", "symbol": "BTC/USD", "side": "buy"}
        ],
        {} # Empty historical data
    )
    return strategy

@pytest.fixture
def mock_portfolio_manager():
    """Creates a mock portfolio manager."""
    pm = MagicMock()
    pm.client.submit_order.return_value = {"id": "123", "status": "filled"}
    return pm

@pytest.fixture
def mock_risk_manager():
    """Creates a mock risk manager."""
    risk_manager = MagicMock()
    risk_manager.calculate_order_qty.return_value = 1.5
    return risk_manager

@pytest.fixture
def app_config():
    """Provides a default AppConfig."""
    return AppConfig(watch_list="BTC/USD", trade_interval="15m")

def test_trader_run(mock_strategy, mock_portfolio_manager, mock_risk_manager, app_config):
    """Tests the main run loop of the Trader."""
    mock_risk_manager.check_for_halt.return_value = False
    trader = Trader(mock_portfolio_manager, mock_strategy, mock_risk_manager, app_config)
    trader.run()

    mock_portfolio_manager.reconcile.assert_called_once()
    mock_strategy.evaluate.assert_called_once()
    mock_portfolio_manager.client.submit_order.assert_called_once()

def test_trader_run_halted(mock_strategy, mock_portfolio_manager, mock_risk_manager, app_config):
    """Tests that the trader does not proceed if risk manager halts."""
    # For this test, we can imagine the halt is already set
    mock_risk_manager.check_for_halt.return_value = True
    trader = Trader(mock_portfolio_manager, mock_strategy, mock_risk_manager, app_config)
    trader.run()

    mock_portfolio_manager.reconcile.assert_called_once()
    # Strategy should not be evaluated if halted
    mock_strategy.evaluate.assert_not_called()

def test_trader_execute_actions_no_actions(mock_strategy, mock_portfolio_manager, mock_risk_manager, app_config):
    """Tests that nothing happens when the strategy returns no actions."""
    mock_strategy.evaluate.return_value = ([], {})
    trader = Trader(mock_portfolio_manager, mock_strategy, mock_risk_manager, app_config)
    trader.run()

    mock_portfolio_manager.client.submit_order.assert_not_called()

def test_trader_execute_order_zero_qty(mock_strategy, mock_portfolio_manager, mock_risk_manager, app_config):
    """Tests that no order is placed when the risk manager returns zero quantity."""
    mock_risk_manager.check_for_halt.return_value = False
    mock_risk_manager.calculate_order_qty.return_value = 0
    mock_strategy.evaluate.return_value = ([{"action": "buy", "symbol": "BTC/USD"}], {})
    trader = Trader(mock_portfolio_manager, mock_strategy, mock_risk_manager, app_config)
    trader.run()

    mock_risk_manager.calculate_order_qty.assert_called_once_with("BTC/USD", "buy")
    mock_portfolio_manager.client.submit_order.assert_not_called()

