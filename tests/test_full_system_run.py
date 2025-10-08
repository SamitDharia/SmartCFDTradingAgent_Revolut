import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from smartcfd.trader import Trader
from smartcfd.strategy import InferenceStrategy
from smartcfd.risk import RiskManager
from smartcfd.portfolio import PortfolioManager, Account
from smartcfd.config import load_config, load_risk_config
from smartcfd.data_loader import DataLoader

# Load configs once
app_config = load_config()
risk_config = load_risk_config()

@pytest.fixture
def mock_portfolio_manager():
    """Fixture to create a mock PortfolioManager."""
    mock_client = MagicMock()
    mock_client.get_account.return_value = Account(
        id="mock_account_id",
        account_number="mock123",
        status="ACTIVE",
        crypto_status="ACTIVE",
        currency="USD",
        buying_power="100000",
        regt_buying_power="100000",
        daytrading_buying_power="100000",
        non_marginable_buying_power="100000",
        cash="50000",
        accrued_fees="0",
        pending_transfer_in="0",
        portfolio_value="50000",
        multiplier="1",
        equity="50000",
        last_equity="50000",
        long_market_value="0",
        short_market_value="0",
        initial_margin="0",
        maintenance_margin="0",
        last_maintenance_margin="0",
        sma="0",
        daytrade_count=0,
        is_online=True
    )
    mock_client.get_all_positions.return_value = []
    
    pm = PortfolioManager(client=mock_client)
    pm.reconcile() # Initialize account and positions
    return pm

@pytest.fixture
def mock_risk_manager(mock_portfolio_manager):
    """Fixture to create a RiskManager with a mock PortfolioManager."""
    return RiskManager(portfolio_manager=mock_portfolio_manager, risk_config=risk_config)

@pytest.fixture
def mock_strategy():
    """Fixture to create a mock InferenceStrategy."""
    # Mock the model and data loader within the strategy
    with patch('joblib.load') as mock_joblib_load, \
         patch('smartcfd.data_loader.DataLoader') as mock_data_loader:
        
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([1]) # Predict 'buy'
        mock_joblib_load.return_value = mock_model
        
        # Configure the mock DataLoader instance
        mock_data_loader_instance = mock_data_loader.return_value
        
        strategy = InferenceStrategy()
        strategy.data_loader = mock_data_loader_instance # Attach the instance for assertions
        
        return strategy

def generate_mock_dataframe(symbol):
    """Generates a realistic-looking DataFrame for a given symbol."""
    dates = pd.to_datetime(pd.date_range(end=pd.Timestamp.now(tz='UTC'), periods=100, freq='H'))
    data = {
        'open': np.random.uniform(95, 105, size=100),
        'high': np.random.uniform(100, 110, size=100),
        'low': np.random.uniform(90, 100, size=100),
        'close': np.random.uniform(98, 108, size=100),
        'volume': np.random.uniform(1000, 5000, size=100),
        'trade_count': np.random.randint(100, 500, size=100),
        'vwap': np.random.uniform(99, 107, size=100),
        'symbol': symbol
    }
    df = pd.DataFrame(data, index=dates)
    # Ensure index is a DatetimeIndex with timezone
    df.index.name = 'timestamp'
    return df

def test_full_system_run_with_good_data(mock_portfolio_manager, mock_risk_manager, mock_strategy):
    """
    Tests the full trader.run() loop with a mock API that returns good data.
    Verifies that a 'buy' order is generated and submitted.
    """
    # Arrange
    # Configure the mock data loader on the strategy to return good data
    mock_data = {
        'BTC/USD': generate_mock_dataframe('BTC/USD'),
        'ETH/USD': generate_mock_dataframe('ETH/USD')
    }
    mock_strategy.data_loader.get_market_data.return_value = mock_data

    # Instantiate the Trader with mocked components
    trader = Trader(
        portfolio_manager=mock_portfolio_manager,
        strategy=mock_strategy,
        risk_manager=mock_risk_manager,
        app_config=app_config
    )

    # Act
    trader.run()

    # Assert
    # 1. Verify that the data loader was called
    mock_strategy.data_loader.get_market_data.assert_called_once()
    
    # 2. Verify that the broker's submit_order method was called
    mock_portfolio_manager.client.submit_order.assert_called()
    
    # 3. Inspect the order that was submitted
    submitted_order = mock_portfolio_manager.client.submit_order.call_args[0][0]
    assert submitted_order.side == 'buy'
    assert submitted_order.symbol in ['BTC/USD', 'ETH/USD']
    assert submitted_order.order_class == 'bracket'
    assert float(submitted_order.qty) > 0

def test_full_system_run_with_no_data(mock_portfolio_manager, mock_risk_manager, mock_strategy, caplog):
    """
    Tests the full trader.run() loop when the data loader returns no data.
    Verifies that no orders are submitted and a warning is logged.
    """
    # Arrange
    # Configure the mock data loader to return an empty dictionary
    mock_strategy.data_loader.get_market_data.return_value = {}

    trader = Trader(
        portfolio_manager=mock_portfolio_manager,
        strategy=mock_strategy,
        risk_manager=mock_risk_manager,
        app_config=app_config
    )

    # Act
    trader.run()

    # Assert
    # 1. Verify that the broker's submit_order method was NOT called
    mock_portfolio_manager.client.submit_order.assert_not_called()
    
    # 2. Check for the expected log message
    assert "trader.run.no_data_from_strategy" in caplog.text

def test_full_system_run_with_api_exception(mock_portfolio_manager, mock_risk_manager, mock_strategy, caplog):
    """
    Tests the full trader.run() loop when the data loader raises an exception.
    Verifies that the error is caught, logged, and no order is submitted.
    """
    # Arrange
    # Configure the mock data loader to raise an exception
    mock_strategy.data_loader.get_market_data.side_effect = Exception("API connection failed")

    trader = Trader(
        portfolio_manager=mock_portfolio_manager,
        strategy=mock_strategy,
        risk_manager=mock_risk_manager,
        app_config=app_config
    )

    # Act
    trader.run()

    # Assert
    # 1. Verify that the broker's submit_order method was NOT called
    mock_portfolio_manager.client.submit_order.assert_not_called()
    
    # 2. Check that the exception was logged at the strategy level and the trader handled it
    assert "inference_strategy.evaluate.data_load_fail" in caplog.text
    assert "trader.run.no_data_from_strategy" in caplog.text
