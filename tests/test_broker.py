import pytest
from unittest.mock import MagicMock

from smartcfd.broker import AlpacaBroker

@pytest.fixture
def mock_alpaca_client():
    """Creates a mock Alpaca client."""
    client = MagicMock()
    client.submit_order.return_value = {"id": "123", "status": "accepted"}
    client.get_account.return_value = {"id": "456", "cash": "100000"}
    client.get_positions.return_value = [{"symbol": "BTC/USD", "qty": "1"}]
    return client

def test_alpaca_broker_submit_order(mock_alpaca_client):
    """Tests that the AlpacaBroker correctly calls the client's submit_order method."""
    broker = AlpacaBroker(mock_alpaca_client)
    order_result = broker.submit_order("BTC/USD", 1.0, "buy", "market", "gtc")

    mock_alpaca_client.submit_order.assert_called_once_with("BTC/USD", 1.0, "buy", "market", "gtc")
    assert order_result["id"] == "123"

def test_alpaca_broker_get_account_info(mock_alpaca_client):
    """Tests that the AlpacaBroker correctly calls the client's get_account method."""
    broker = AlpacaBroker(mock_alpaca_client)
    account_info = broker.get_account_info()

    mock_alpaca_client.get_account.assert_called_once()
    assert account_info["id"] == "456"

def test_alpaca_broker_list_positions(mock_alpaca_client):
    """Tests that the AlpacaBroker correctly calls the client's get_positions method."""
    broker = AlpacaBroker(mock_alpaca_client)
    positions = broker.list_positions()

    mock_alpaca_client.get_positions.assert_called_once()
    assert len(positions) == 1
    assert positions[0]["symbol"] == "BTC/USD"
