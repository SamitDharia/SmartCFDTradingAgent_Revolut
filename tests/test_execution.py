import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np

from smartcfd.trader import Trader
from smartcfd.strategy import InferenceStrategy
from smartcfd.portfolio import PortfolioManager
from smartcfd.risk import RiskManager
from smartcfd.config import AppConfig, AlpacaConfig, RiskConfig
from smartcfd.regime_detector import MarketRegime

@pytest.fixture
def mock_config():
    """Fixture for a mock AppConfig."""
    app_config = AppConfig(
        alpaca_env='paper',
        min_data_points=100,
        trade_confidence_threshold=0.51,
        watch_list="BTC/USD",
        trade_interval='1m'
    )
    return app_config

@pytest.fixture
def mock_alpaca_config():
    """Fixture for a mock AlpacaConfig."""
    return AlpacaConfig(api_key='test', secret_key='test')

@pytest.fixture
def mock_risk_config():
    """Fixture for a mock RiskConfig."""
    return RiskConfig(
        max_daily_drawdown_percent=-10.0,
        risk_per_trade_percent=1.0,
        stop_loss_atr_multiplier=1.5,
        take_profit_atr_multiplier=3.0,
        min_order_notional=0.0,
    )

@pytest.mark.integration
@patch('smartcfd.trader.DataLoader')
@patch('smartcfd.alpaca_client.AlpacaBroker')
def test_force_buy_execution(MockAlpacaBroker, MockDataLoader, mock_config, mock_alpaca_config, mock_risk_config):
    """
    Tests the full end-to-end execution of a BUY order by forcing a high-confidence signal.
    """
    # Mock historical data for ATR calculation
    dates = pd.to_datetime(pd.date_range(end='now', periods=100, freq='min', tz='UTC'))
    data = {'high': 50100, 'low': 49900, 'close': 50050}
    historical_df = pd.DataFrame(data, index=dates)

    # 1. Setup Mocks
    mock_data_loader = MockDataLoader.return_value
    mock_data_loader.get_market_data.return_value = {'BTC/USD': historical_df}

    mock_broker = MockAlpacaBroker.return_value
    mock_broker.get_account.return_value = MagicMock(
        cash='100000',
        equity='100000',
        buying_power='200000'
    )
    mock_broker.get_open_positions.return_value = []
    mock_broker.get_open_orders.return_value = []
    mock_broker.get_crypto_snapshot.return_value = {'BTC/USD': MagicMock(latest_quote=MagicMock(ap=50000, bp=49999))}

    # 2. Setup Strategy with a Mocked Model
    strategy = InferenceStrategy(config=mock_config, trade_confidence_threshold=0.51)
    strategy.model = MagicMock()
    
    # Force a BUY signal (class 1) with high confidence (e.g., 95%)
    strategy.model.predict.return_value = np.array([1]) 
    strategy.model.predict_proba.return_value = np.array([[0.04, 0.95, 0.01]]) # [hold, buy, sell]

    # Mock feature names loading
    with patch('joblib.load', return_value=['feature_a', 'feature_b']):
        strategy.feature_names = ['feature_a', 'feature_b']

    # 3. Setup Core Components
    portfolio = PortfolioManager(client=mock_broker)
    risk_manager = RiskManager(portfolio_manager=portfolio, risk_config=mock_risk_config)
    
    trader = Trader(
        portfolio_manager=portfolio,
        strategy=strategy,
        risk_manager=risk_manager,
        app_config=mock_config,
        alpaca_config=mock_alpaca_config,
        regime_detector=MagicMock()
    )


    # 4. Run the Trader
    trader.run()

    # 5. Assertions
    # Verify that submit_order was called
    mock_broker.submit_order.assert_called_once()
    
    # Check the arguments of the call
    call_args = mock_broker.submit_order.call_args
    
    # The actual call is submit_order(order_request: OrderRequest)
    # So we need to check the attributes of the OrderRequest object
    order_request_arg = call_args.args[0]
    
    assert order_request_arg.symbol == 'BTC/USD'
    assert float(order_request_arg.qty) > 0
    assert order_request_arg.side == 'buy'
    assert order_request_arg.time_in_force == 'gtc'
    assert order_request_arg.take_profit is not None
    assert order_request_arg.stop_loss is not None

