import pytest
from unittest.mock import MagicMock
from smartcfd.strategy import DryRunStrategy, StrategyHarness, get_strategy_by_name

@pytest.fixture
def mock_alpaca_client():
    """Fixture to create a mock AlpacaClient."""
    client = MagicMock()
    client.api_base = "https://paper-api.alpaca.markets"
    return client

def test_dry_run_strategy_evaluate(mock_alpaca_client):
    """
    Verify that the DryRunStrategy returns a list of log actions.
    """
    strategy = DryRunStrategy()
    actions = strategy.evaluate(mock_alpaca_client)
    
    assert isinstance(actions, list)
    assert len(actions) == 3
    assert all(a["action"] == "log" and a["decision"] == "hold" for a in actions)
    assert actions[0]["symbol"] == "AAPL"

def test_strategy_harness_run(mock_alpaca_client):
    """
    Verify that the StrategyHarness calls the strategy's evaluate method.
    """
    # Create a mock strategy
    mock_strategy = MagicMock()
    mock_strategy.evaluate.return_value = [{"action": "test"}]
    
    harness = StrategyHarness(mock_alpaca_client, mock_strategy)
    harness.run()
    
    # Assert that the strategy's evaluate method was called once
    mock_strategy.evaluate.assert_called_once_with(mock_alpaca_client)

def test_get_strategy_by_name():
    """
    Verify that the strategy factory returns the correct strategy instance.
    """
    strategy = get_strategy_by_name("dry_run")
    assert isinstance(strategy, DryRunStrategy)
    
    with pytest.raises(ValueError):
        get_strategy_by_name("non_existent_strategy")
