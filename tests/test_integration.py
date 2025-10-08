import unittest
from unittest.mock import MagicMock, patch
import pandas as pd

from smartcfd.trader import Trader
from smartcfd.portfolio import PortfolioManager, Account, Position
from smartcfd.strategy import get_strategy_by_name, InferenceStrategy
from smartcfd.risk import RiskManager
from smartcfd.config import RiskConfig, AppConfig

class TestFullTradingLoop(unittest.TestCase):
    def setUp(self):
        """Set up the full trading loop with mocked components."""
        self.mock_client = MagicMock()
        self.mock_client.feed = 'iex'  # Set feed on the mock client
        self.mock_model = MagicMock()

        # Mock configurations
        self.app_config = AppConfig(
            watch_list='BTC/USD,ETH/USD',
            trade_interval="1h",
            max_data_staleness_minutes=30,
            feed='iex'  # Add the missing feed attribute
        )
        self.risk_config = RiskConfig(
            risk_per_trade_percent=1.0,  # 1%
            max_total_exposure_percent=50.0,  # 50%
            max_exposure_per_asset_percent=25.0,  # 25%
            max_daily_drawdown_percent=-5.0,
            circuit_breaker_atr_multiplier=2.5,
            min_order_notional=1.0,  # Add min_order_notional
        )

        # Set the feed on the mock client to match the app_config
        self.mock_client.feed = self.app_config.feed

        # Real components, but with mocked dependencies
        self.portfolio_manager = PortfolioManager(self.mock_client)

        # --- Mock broker ---
        self.mock_broker = MagicMock()

        # --- Mock data loading ---
        self.mock_data_loader = MagicMock()
        timestamps = pd.to_datetime(pd.date_range(end=pd.Timestamp.now(tz='UTC'), periods=200, freq='1min'))
        mock_df = pd.DataFrame({
            'open': [100 + i*0.01 for i in range(200)],
            'high': [101 + i*0.01 for i in range(200)],
            'low': [99 + i*0.01 for i in range(200)],
            'close': [100.5 + i*0.01 for i in range(200)],
            'volume': [1000 for _ in range(200)]
        }, index=timestamps)
        self.mock_data_loader.get_market_data.return_value = {
            "BTC/USD": mock_df,
            "ETH/USD": mock_df.copy()
        }

        # --- Trader Setup ---
        self.strategy = InferenceStrategy(
            model_path="dummy/model.joblib",
            data_loader=self.mock_data_loader
        )
        self.strategy.model = self.mock_model # Replace the loaded model with our mock

        # Patch the price feed used by the RiskManager (on the broker)
        self.mock_latest_trade = MagicMock(return_value={'trade': {'p': 50000.0}})
        patcher_price = patch.object(self.mock_broker, 'get_latest_crypto_trade', self.mock_latest_trade)
        self.addCleanup(patcher_price.stop)
        patcher_price.start()

        self.risk_manager = RiskManager(self.portfolio_manager, self.risk_config, broker=self.mock_broker)
        self.trader = Trader(
            portfolio_manager=self.portfolio_manager,
            strategy=self.strategy,
            risk_manager=self.risk_manager,
            app_config=self.app_config,
        )
        self.trader.broker.submit_order = MagicMock()


    def _setup_common_mocks(self):
        """Sets up common mock return values for a typical trade cycle."""
        # --- Portfolio Manager Mocks ---
        # The client returns an object with attributes, not a dict. Pydantic models can handle this.
        mock_account = MagicMock()
        mock_account.id = "test_id"
        mock_account.equity = 100000.0
        mock_account.last_equity = 100000.0
        mock_account.buying_power = 200000.0
        mock_account.cash = 100000.0
        mock_account.status = "ACTIVE"
        
        # The portfolio manager expects the client to return the raw object from the API
        self.portfolio_manager.client.get_account.return_value = mock_account
        
        # By default, no open positions or orders
        self.portfolio_manager.client.get_positions.return_value = []
        self.portfolio_manager.client.get_orders.return_value = []

        # --- Feature Calculation Mock ---
        mock_features = pd.DataFrame([{'feature1': 1, 'feature2': 2}])
        patcher_features = patch('smartcfd.strategy.create_features', return_value=mock_features)
        self.addCleanup(patcher_features.stop)
        patcher_features.start()

    def test_buy_signal_for_one_asset_in_watchlist(self):
        """
        Tests the full loop with a multi-asset watchlist where the strategy
        generates a 'buy' for one asset and 'hold' for another.
        """
        self._setup_common_mocks()

        # --- Behavior-specific Mocks ---
        # Strategy mock: model predicts 'buy' (1) for BTC/USD and 'hold' (0) for ETH/USD
        self.mock_model.predict.side_effect = [[1], [0]]
        
        # Client mock: submit_order should be called and return a mock order confirmation
        mock_order_confirmation = MagicMock()
        mock_order_confirmation.id = "new_order_123"
        self.trader.broker.submit_order.return_value = mock_order_confirmation
        
        # Set price for BTC/USD
        self.mock_latest_trade.return_value = {'trade': {'p': 50000.0}}

        # --- Run the trading loop ---
        self.trader.run()

        # --- Assertions ---
        # 1. Portfolio was reconciled
        self.portfolio_manager.client.get_account.assert_called_once()
        self.portfolio_manager.client.get_positions.assert_called_once()

        # 2. Strategy was evaluated for both symbols
        self.assertEqual(self.mock_data_loader.get_market_data.call_count, 2)
        self.assertEqual(self.mock_model.predict.call_count, 2)

        # 3. Risk was managed only for the 'buy' signal (BTC/USD)
        self.mock_latest_trade.assert_called_once_with('BTC/USD', self.app_config.feed)

        # 4. Order was submitted only for the 'buy' signal
        self.trader.broker.submit_order.assert_called_once()
        call_args = self.trader.broker.submit_order.call_args
        order_request = call_args.args[0]
        self.assertEqual(order_request.symbol, 'BTC/USD')
        self.assertEqual(order_request.side, 'buy')
        
        # Expected qty = (100,000 * 1%) / 50,000 = 0.02
        self.assertAlmostEqual(float(order_request.qty), 0.02)

    def test_buy_signal_when_one_position_exists(self):
        """
        Tests a multi-asset scenario where a position exists for one asset (BTC/USD)
        but not the other (ETH/USD). Expect a 'buy' order only for ETH/USD.
        """
        self._setup_common_mocks()

        # --- Behavior-specific Mocks ---
        # Mock an existing position for BTC/USD
        existing_position = MagicMock(spec=Position)
        existing_position.symbol = "BTC/USD"
        existing_position.qty = 0.2
        existing_position.market_value = 10000.0 # 10% of equity
        existing_position.unrealized_pl = 0.0
        existing_position.unrealized_plpc = 0.0
        existing_position.avg_entry_price = 50000.0
        existing_position.side = "long"
        self.portfolio_manager.client.get_positions.return_value = [existing_position]

        # Strategy mock: model predicts 'buy' (1) for both symbols
        self.mock_model.predict.side_effect = [[1], [1]]
        
        # Client mock for the ETH/USD order
        mock_order_confirmation = MagicMock()
        mock_order_confirmation.id = "new_order_eth_456"
        self.trader.broker.submit_order.return_value = mock_order_confirmation
        
        # Set price for ETH/USD
        self.mock_latest_trade.return_value = {'trade': {'p': 3000.0}}

        # --- Run the trading loop ---
        self.trader.run()

        # --- Assertions ---
        # 2. Strategy was evaluated for both symbols
        self.assertEqual(self.mock_data_loader.get_market_data.call_count, 2)
        self.assertEqual(self.mock_model.predict.call_count, 2)

        # 3. Risk was managed for both potential trades, and orders were submitted for both
        self.assertEqual(self.mock_latest_trade.call_count, 2)
        self.mock_latest_trade.assert_any_call('BTC/USD', self.app_config.feed)
        self.mock_latest_trade.assert_any_call('ETH/USD', self.app_config.feed)
        self.assertEqual(self.trader.broker.submit_order.call_count, 2)
        call_args = self.trader.broker.submit_order.call_args
        order_request = call_args.args[0]
        self.assertEqual(order_request.symbol, 'ETH/USD')
        
        # Expected qty = (100,000 * 1%) / 3,000 = 0.33333333
        self.assertAlmostEqual(float(order_request.qty), 0.33333333)

    def test_order_blocked_by_total_exposure(self):
        """
        Tests that a new order is blocked if it would exceed the
        max_total_exposure_percent limit.
        """
        self._setup_common_mocks()
        
        # --- Behavior-specific Mocks ---
        # Existing positions worth $49,500 (49.5% of $100k equity), near the 50% total limit
        pos1 = MagicMock(spec=Position)
        pos1.symbol = "LINK/USD"
        pos1.qty = 1000.0; pos1.market_value = 25000.0; pos1.unrealized_pl = 0.0; pos1.unrealized_plpc = 0.0; pos1.avg_entry_price = 25.0; pos1.side = "long"
        pos2 = MagicMock(spec=Position)
        pos2.symbol = "SOL/USD"
        pos2.qty = 100.0; pos2.market_value = 24500.0; pos2.unrealized_pl = 0.0; pos2.unrealized_plpc = 0.0; pos2.avg_entry_price = 245.0; pos2.side = "long"
        self.portfolio_manager.client.get_positions.return_value = [pos1, pos2]
        
        # Strategy predicts 'buy' for BTC/USD
        self.mock_model.predict.side_effect = [[1], [0]]
        self.mock_latest_trade.return_value = {'trade': {'p': 50000.0}}

        # --- Run the trading loop ---
        self.trader.run()

        # --- Assertions ---
        # Total exposure headroom is only $500.
        # $500 / $50,000 price = 0.01 qty.
        # This is a notional value of $500, which is above the $1 minimum.
        self.trader.broker.submit_order.assert_called_once()
        call_args = self.trader.broker.submit_order.call_args
        order_request = call_args.args[0]
        
        # Max total exposure = 50% of $100k = $50,000
        # Current exposure = $49,500
        # Headroom = $500
        # Order qty = $500 / $50,000 price = 0.01
        self.assertAlmostEqual(float(order_request.qty), 0.01)
        self.assertEqual(order_request.symbol, 'BTC/USD')

    def test_order_limited_by_asset_exposure(self):
        """
        Tests that a new order is correctly sized down to respect the
        max_exposure_per_asset_percent limit.
        """
        self._setup_common_mocks()
        
        # --- Behavior-specific Mocks ---
        # Strategy predicts 'buy' for both assets, but we only care about BTC
        self.mock_model.predict.side_effect = [[1], [0]]

        # Existing BTC position worth $24,000 (24% of $100k equity)
        existing_position = MagicMock(spec=Position)
        existing_position.symbol = "BTC/USD"
        existing_position.qty = 0.48
        existing_position.market_value = 24000.0
        existing_position.unrealized_pl = 0.0
        existing_position.unrealized_plpc = 0.0
        existing_position.avg_entry_price = 50000.0
        existing_position.side = "long"
        self.portfolio_manager.client.get_positions.return_value = [existing_position]
        
        self.mock_latest_trade.return_value = {'trade': {'p': 50000.0}}

        # --- Run the trading loop ---
        self.trader.run()

        # --- Assertions ---
        # The new logic should place an order to increase the position up to the limit.
        self.trader.broker.submit_order.assert_called_once()

        # Verify the submitted order has the correct, limited quantity
        call_args, _ = self.trader.broker.submit_order.call_args
        order_request = call_args[0]
        self.assertEqual(order_request.symbol, 'BTC/USD')
        self.assertEqual(float(order_request.qty), 0.02)
        call_args = self.trader.broker.submit_order.call_args
        order_request = call_args.args[0]
        
        # Max asset exposure = 25% of $100k = $25,000
        # Current exposure = $24,000
        # Headroom = $1,000
        # Order qty = $1,000 / $50,000 price = 0.02
        self.assertAlmostEqual(float(order_request.qty), 0.02)

    def test_short_sell_signal_for_one_asset(self):
        """
        Tests the full loop for a short-selling scenario where the strategy
        generates a 'sell' signal for one asset.
        """
        self._setup_common_mocks()

        # --- Behavior-specific Mocks ---
        # Strategy mock: model predicts 'sell' (2) for BTC/USD and 'hold' (0) for ETH/USD
        self.mock_model.predict.side_effect = [[2], [0]]
        
        # Client mock: submit_order should be called and return a mock order confirmation
        mock_order_confirmation = MagicMock()
        mock_order_confirmation.id = "new_short_order_789"
        self.trader.broker.submit_order.return_value = mock_order_confirmation
        
        # Set price for BTC/USD
        self.mock_latest_trade.return_value = {'trade': {'p': 50000.0}}

        # --- Run the trading loop ---
        self.trader.run()

        # --- Assertions ---
        # 1. Portfolio was reconciled
        self.portfolio_manager.client.get_account.assert_called_once()

        # 2. Strategy was evaluated for both symbols
        self.assertEqual(self.mock_data_loader.get_market_data.call_count, 2)
        self.assertEqual(self.mock_model.predict.call_count, 2)

        # 3. Risk was managed for the 'sell' signal
        self.mock_latest_trade.assert_called_once_with('BTC/USD', self.app_config.feed)

        # 4. A 'sell' order was submitted
        self.trader.broker.submit_order.assert_called_once()
        call_args = self.trader.broker.submit_order.call_args
        order_request = call_args.args[0]
        self.assertEqual(order_request.symbol, 'BTC/USD')
        self.assertEqual(order_request.side, 'sell')
        self.assertAlmostEqual(float(order_request.qty), 0.02)

    def test_no_action_on_hold_signal(self):
        """
        Tests that no action is taken when the strategy signals 'hold' for all assets.
        """
        self._setup_common_mocks()

        # --- Behavior-specific Mocks ---
        # Strategy mock: model predicts 'hold' (0) for both assets
        self.mock_model.predict.side_effect = [[0], [0]]
        
        # --- Run the trading loop ---
        self.trader.run()

        # --- Assertions ---
        # 1. Portfolio was reconciled
        self.portfolio_manager.client.get_account.assert_called_once()
        self.portfolio_manager.client.get_positions.assert_called_once()

        # 2. Strategy was evaluated for both symbols
        self.assertEqual(self.mock_data_loader.get_market_data.call_count, 2)
        self.assertEqual(self.mock_model.predict.call_count, 2)

        # 3. Risk was not managed (no trades)
        self.mock_latest_trade.assert_not_called()
        self.trader.broker.submit_order.assert_not_called()


if __name__ == '__main__':
    unittest.main()
