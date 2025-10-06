import pytest
import requests
import requests_mock
from unittest.mock import MagicMock
from smartcfd.trader import TradingSession

def test_trading_session_initialization():
    """Verify that the TradingSession can be initialized."""
    mock_harness = MagicMock()
    session = TradingSession("http://test.com", 1, mock_harness)
    assert session.api_base == "http://test.com"
    assert session.timeout == 1
    assert session.harness is mock_harness

@pytest.fixture
def session():
    """Fixture to create a TradingSession with a mock adapter."""
    api_base = "https://paper-api.alpaca.markets"
    timeout = 5
    # Create a mock harness for the session
    mock_harness = MagicMock()
    return TradingSession(api_base, timeout, mock_harness)

def test_is_market_open_true(session, requests_mock):
    """Verify is_market_open returns True when the API says so."""
    requests_mock.get(f"{session.api_base}/v2/clock", json={"is_open": True})
    assert session.is_market_open() is True

def test_is_market_open_false(session, requests_mock):
    """Verify is_market_open returns False when the API says so."""
    requests_mock.get(f"{session.api_base}/v2/clock", json={"is_open": False})
    assert session.is_market_open() is False

def test_is_market_open_api_error(session, requests_mock):
    """Verify is_market_open returns False on API error."""
    requests_mock.get(f"{session.api_base}/v2/clock", status_code=500)
    assert session.is_market_open() is False

def test_run_strategy_when_market_open(session, requests_mock):
    """Verify the strategy runs when the market is open."""
    requests_mock.get(f"{session.api_base}/v2/clock", json={"is_open": True})
    
    session.run_strategy_if_market_open()
    
    # Verify that the harness's run method was called
    session.harness.run.assert_called_once()

def test_do_not_run_strategy_when_market_closed(session, requests_mock):
    """Verify the strategy does not run when the market is closed."""
    requests_mock.get(f"{session.api_base}/v2/clock", json={"is_open": False})
    
    session.run_strategy_if_market_open()
    
    # Verify that the harness's run method was NOT called
    session.harness.run.assert_not_called()
    
    # Mock the strategy to track if it was called
    strategy_called = False
    def mock_strategy(s):
        nonlocal strategy_called
        strategy_called = True
        return {"action": "test"}
    
    session.strategy = mock_strategy
    session.run_strategy_if_market_open()
    
    assert strategy_called is False
