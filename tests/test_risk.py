import pytest
from unittest.mock import MagicMock
import pandas as pd

from smartcfd.data_loader import DataLoader
from smartcfd.risk import RiskManager, Account, Position
from smartcfd.config import RiskConfig
from smartcfd.alpaca_client import AlpacaClient, get_alpaca_client

@pytest.fixture
def risk_config():
    """Provides a default RiskConfig for tests."""
    return RiskConfig(
        max_daily_drawdown_percent=-0.05,  # Represents -5%
        circuit_breaker_atr_multiplier=3.0,
        risk_per_trade_percent=0.01, # Represents 1%
    )

@pytest.fixture
def alpaca_client():
    """Provides an AlpacaClient instance for tests."""
    return get_alpaca_client("http://mock.alpaca.api")

@pytest.fixture
def data_loader():
    """Provides a DataLoader instance for tests."""
    return DataLoader("http://mock.alpaca.api")

@pytest.fixture
def risk_manager(risk_config):
    """Provides a RiskManager with a properly mocked client and data_loader."""
    # Create a mock client that has the methods we expect to call
    mock_client = MagicMock(spec=AlpacaClient)
    mock_client.get_account = MagicMock()
    
    mock_data_loader = MagicMock(spec=DataLoader)
    mock_data_loader.get_market_data = MagicMock()

    return RiskManager(client=mock_client, data_loader=mock_data_loader, config=risk_config)

def test_check_for_halt_no_drawdown(risk_manager):
    """
    Verify that trading is NOT halted when drawdown is within limits.
    """
    mock_account = Account(equity="100000", last_equity="100000", buying_power="200000")
    risk_manager.client.get_account.return_value = mock_account
    risk_manager.data_loader.get_market_data.return_value = None # Assume no volatility issues

    assert not risk_manager.check_for_halt(watch_list=["BTC/USD"], interval="15m")

def test_check_for_halt_drawdown_exceeded(risk_manager):
    """
    Verify that trading IS halted when the max daily drawdown is exceeded.
    """
    # 6% drawdown (94000 equity from 100000) exceeds the -5% limit
    mock_account = Account(equity="94000", last_equity="100000", buying_power="200000")
    risk_manager.client.get_account.return_value = mock_account
    risk_manager.data_loader.get_market_data.return_value = None # Assume no volatility issues

    assert risk_manager.check_for_halt(watch_list=["BTC/USD"], interval="15m")
    assert risk_manager.is_halted
    assert "Max daily drawdown exceeded" in risk_manager.halt_reason

def test_check_for_halt_drawdown_not_a_number(risk_manager):
    """
    Verify that trading is halted and reason is set when account equity is not a number.
    """
    mock_account = Account(equity="N/A", last_equity="100000", buying_power="200000")
    risk_manager.client.get_account.return_value = mock_account

    assert risk_manager.check_for_halt(watch_list=["BTC/USD"], interval="15m")
    assert risk_manager.is_halted
    assert risk_manager.halt_reason == "Could not calculate drawdown due to invalid account data."
def test_circuit_breaker_disabled(risk_manager):
    """Verify that if the multiplier is 0, the check is skipped."""
    risk_manager.config.circuit_breaker_atr_multiplier = 0
    halted = risk_manager._check_volatility_for_symbol("BTC/USD", "15m")
    assert not halted
    assert not risk_manager.is_halted

def test_circuit_breaker_no_data(risk_manager, data_loader):
    """Verify the check handles cases where the data loader returns no data."""
    risk_manager.config.circuit_breaker_atr_multiplier = 3.0
    data_loader.get_market_data = MagicMock(return_value=None)
    halted = risk_manager._check_volatility_for_symbol("BTC/USD", "15m")
    assert not halted
    assert not risk_manager.is_halted

def test_circuit_breaker_normal_volatility(risk_manager, data_loader):
    """Verify the circuit breaker is NOT triggered during normal volatility."""
    risk_manager.config.circuit_breaker_atr_multiplier = 3.5
    
    # Create a mock dataframe with normal volatility
    mock_data = pd.DataFrame({
        'high':  [105, 106, 105.5, 106.5, 107],
        'low':   [103, 104, 103.5, 104.5, 105],
        'close': [104, 105, 104.5, 105.5, 106],
    }, index=pd.to_datetime(['2023-01-01 09:00', '2023-01-01 09:15', '2023-01-01 09:30', '2023-01-01 09:45', '2023-01-01 10:00']))
    
    data_loader.get_market_data = MagicMock(return_value=mock_data)

    halted = risk_manager._check_volatility_for_symbol("BTC/USD", "15m")
    assert not halted
    assert not risk_manager.is_halted

def test_circuit_breaker_tripped_by_high_volatility(risk_manager):
    """Verify the circuit breaker IS triggered when volatility spikes."""
    risk_manager.config.circuit_breaker_atr_multiplier = 2.0 # Lower multiplier for test
    
    # Create a mock dataframe where the last bar has extreme range
    mock_data = pd.DataFrame({
        'high':  [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 120],
        'low':   [99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 100],
        'close': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 110],
    }, index=pd.to_datetime(pd.date_range(start='2023-01-01', periods=16, freq='15min')))
    
    risk_manager.data_loader.get_market_data.return_value = mock_data

    halted = risk_manager._check_volatility_for_symbol("BTC/USD", "15m")
    assert halted
    assert risk_manager.is_halted
    assert "Volatility circuit breaker tripped" in risk_manager.halt_reason

def test_check_for_halt_integrates_volatility_check(risk_manager):
    """Verify the main halt check calls the volatility check."""
    # Mock account info to pass the drawdown check
    mock_account = Account(equity="100000", last_equity="100000", buying_power="200000")
    risk_manager.client.get_account.return_value = mock_account

    # Mock the volatility check to return True
    risk_manager._check_volatility_for_symbol = MagicMock(return_value=True)

    halted = risk_manager.check_for_halt(["BTC/USD"], "15m")

    assert halted
    risk_manager._check_volatility_for_symbol.assert_called_once_with("BTC/USD", "15m")
    assert risk_manager.is_halted

def test_risk_manager_resets_halt_after_success(risk_manager):
    """
    Test that the RiskManager resets its halt status after a successful check
    when the conditions for halting are no longer met.
    """
    # 1. Initial state: simulate a halt due to drawdown
    risk_manager.is_halted = True
    risk_manager.halt_reason = "Max daily drawdown exceeded: -6.00% < -5.0%"

    # 2. Mock account info to show recovery from drawdown
    mock_account_recovered = Account(equity="100000", last_equity="100000", buying_power="200000")
    risk_manager.client.get_account.return_value = mock_account_recovered

    # 3. Ensure that the next check detects no volatility issues
    risk_manager.data_loader.get_market_data.return_value = None

    # 4. Action: Run the check. The function should now see that conditions are fine and reset the halt.
    halted = risk_manager.check_for_halt(watch_list=["BTC/USD"], interval="15m")

    # 5. Assertions
    assert not halted, "The system should no longer be halted as drawdown is resolved."
    assert not risk_manager.is_halted, "The is_halted flag should be reset to False."
    assert risk_manager.halt_reason == "", "The halt reason should be cleared."
