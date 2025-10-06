import pytest
import requests
import requests_mock
from smartcfd.trader import TradingSession, example_strategy

@pytest.fixture
def session():
    """Fixture to create a TradingSession with a mock adapter."""
    api_base = "https://paper-api.alpaca.markets"
    timeout = 5
    return TradingSession(api_base, timeout, example_strategy)

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
    
    # Mock the strategy to track if it was called
    strategy_called = False
    def mock_strategy(s):
        nonlocal strategy_called
        strategy_called = True
        return {"action": "test"}
    
    session.strategy = mock_strategy
    session.run_strategy_if_market_open()
    
    assert strategy_called is True

def test_do_not_run_strategy_when_market_closed(session, requests_mock):
    """Verify the strategy does not run when the market is closed."""
    requests_mock.get(f"{session.api_base}/v2/clock", json={"is_open": False})
    
    # Mock the strategy to track if it was called
    strategy_called = False
    def mock_strategy(s):
        nonlocal strategy_called
        strategy_called = True
        return {"action": "test"}
    
    session.strategy = mock_strategy
    session.run_strategy_if_market_open()
    
    assert strategy_called is False
