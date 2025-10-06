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
    trader = Trader(mock_strategy, mock_broker, mock_risk_manager)
    trader.run()

    mock_strategy.evaluate.assert_called_once()
    mock_broker.submit_order.assert_called_once_with(
        symbol="BTC/USD",
        qty=1.5,
        side="buy",
        order_type="market",
        time_in_force="gtc"
    )
    mock_risk_manager.calculate_order_qty.assert_called_once_with("BTC/USD", "buy")

def test_trader_execute_actions_no_actions(mock_strategy, mock_broker, mock_risk_manager):
    """Tests that nothing happens when the strategy returns no actions."""
    mock_strategy.evaluate.return_value = []
    trader = Trader(mock_strategy, mock_broker, mock_risk_manager)
    trader.run()

    mock_broker.submit_order.assert_not_called()

def test_trader_execute_order_zero_qty(mock_strategy, mock_broker, mock_risk_manager):
    """Tests that no order is placed when the risk manager returns zero quantity."""
    mock_risk_manager.calculate_order_qty.return_value = 0
    trader = Trader(mock_strategy, mock_broker, mock_risk_manager)
    trader.run()

    mock_broker.submit_order.assert_not_called()

