import pytest
from unittest.mock import MagicMock

from smartcfd.trader import Trader

@pytest.fixture
def mock_strategy():
    """Creates a mock strategy."""
    strategy = MagicMock()
    strategy.evaluate.return_value = [
        {"action": "log", "message": "Holding position."},
        {"action": "order", "symbol": "BTC/USD", "side": "buy"}
    ]
    return strategy

@pytest.fixture
def mock_broker():
    """Creates a mock broker."""
    broker = MagicMock()
    broker.submit_order.return_value = {"id": "123", "status": "filled"}
    return broker

@pytest.fixture
def mock_risk_manager():
    """Creates a mock risk manager."""
    risk_manager = MagicMock()
    risk_manager.calculate_order_qty.return_value = 1.5
    return risk_manager

def test_trader_run(mock_strategy, mock_broker, mock_risk_manager):
    """Tests the main run loop of the Trader."""
    mock_risk_manager.check_for_halt.return_value = False
    trader = Trader(mock_strategy, mock_broker, mock_risk_manager)
    trader.run(watch_list=["BTC/USD"], interval="15m")

    mock_risk_manager.check_for_halt.assert_called_once()
    mock_strategy.evaluate.assert_called_once()
    mock_broker.submit_order.assert_not_called() # Assuming evaluate returns no actions

def test_trader_run_halted(mock_strategy, mock_broker, mock_risk_manager):
    """Tests that the trader does not proceed if risk manager halts."""
    mock_risk_manager.check_for_halt.return_value = True
    trader = Trader(mock_strategy, mock_broker, mock_risk_manager)
    trader.run(watch_list=["BTC/USD"], interval="15m")

    mock_risk_manager.check_for_halt.assert_called_once()
    mock_strategy.evaluate.assert_not_called()

def test_trader_execute_actions_no_actions(mock_strategy, mock_broker, mock_risk_manager):
    """Tests that nothing happens when the strategy returns no actions."""
    mock_strategy.evaluate.return_value = []
    mock_risk_manager.check_for_halt.return_value = False
    trader = Trader(mock_strategy, mock_broker, mock_risk_manager)
    trader.run(watch_list=["BTC/USD"], interval="15m")

    mock_broker.submit_order.assert_not_called()

def test_trader_execute_order_zero_qty(mock_strategy, mock_broker, mock_risk_manager):
    """Tests that no order is placed when the risk manager returns zero quantity."""
    mock_risk_manager.calculate_order_qty.return_value = 0
    mock_risk_manager.check_for_halt.return_value = False
    mock_strategy.evaluate.return_value = [{"action": "buy", "symbol": "BTC/USD"}]
    trader = Trader(mock_strategy, mock_broker, mock_risk_manager)
    trader.run(watch_list=["BTC/USD"], interval="15m")

    mock_risk_manager.calculate_order_qty.assert_called_once_with("BTC/USD", "buy")
    mock_broker.submit_order.assert_not_called()

