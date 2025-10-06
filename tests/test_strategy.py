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
    # Create a mock strategy and risk manager
    mock_strategy = MagicMock()
    mock_strategy.evaluate.return_value = [{"action": "test"}]
    mock_risk_manager = MagicMock()
    mock_risk_manager.check_for_halt.return_value = False
    mock_risk_manager.filter_actions.side_effect = lambda actions: actions

    harness = StrategyHarness(mock_alpaca_client, mock_strategy, mock_risk_manager)
    harness.run()

    # Assert that the strategy's evaluate method was called once
    mock_strategy.evaluate.assert_called_once_with(mock_alpaca_client)
    # Assert that the risk manager was consulted
    mock_risk_manager.check_for_halt.assert_called_once()
    mock_risk_manager.filter_actions.assert_called_once()

def test_get_strategy_by_name():
    """
    Verify that the strategy factory returns the correct strategy instance.
    """
    strategy = get_strategy_by_name("dry_run")
    assert isinstance(strategy, DryRunStrategy)
    
    with pytest.raises(ValueError):
        get_strategy_by_name("non_existent_strategy")
