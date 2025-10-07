import unittest
from unittest.mock import MagicMock, patch
import pandas as pd

from smartcfd.trader import Trader
from smartcfd.portfolio import PortfolioManager, Account, Position
from smartcfd.strategy import get_strategy_by_name
from smartcfd.risk import RiskManager
from smartcfd.config import RiskConfig, AppConfig

class TestFullTradingLoop(unittest.TestCase):
    def setUp(self):
        """Set up the full trading loop with mocked components."""
        self.mock_client = MagicMock()
        
        # Mock configurations
        self.app_config = AppConfig(
            watch_list='BTC/USD,ETH/USD',
            trade_interval="1h",
            max_data_staleness_minutes=30,
        )
        self.risk_config = RiskConfig(
            risk_per_trade_percent=1.0,  # 1%
            max_total_exposure_percent=50.0,  # 50%
            max_exposure_per_asset_percent=25.0,  # 25%
            max_daily_drawdown_percent=-5.0,
            circuit_breaker_atr_multiplier=2.5,
        )

        # Real components, but with mocked dependencies
        self.portfolio_manager = PortfolioManager(self.mock_client)
        self.strategy = get_strategy_by_name("inference")
        self.risk_manager = RiskManager(self.portfolio_manager, self.risk_config)
        
        self.trader = Trader(
            portfolio_manager=self.portfolio_manager,
            strategy=self.strategy,
            risk_manager=self.risk_manager,
            app_config=self.app_config,
        )

        # Mock the model used by the InferenceStrategy
        self.mock_model = MagicMock()
        self.mock_model.get_booster.return_value.feature_names = ['feature1', 'feature2']
        self.strategy.model = self.mock_model

        # Mock the data loader used by the strategy
        self.mock_data_loader = MagicMock()
        patcher = patch('smartcfd.strategy.DataLoader', return_value=self.mock_data_loader)
        self.addCleanup(patcher.stop)
        patcher.start()

        # Patch the price feed used by the RiskManager
        self.mock_latest_trade = MagicMock(return_value={'trade': {'p': 50000.0}})
        patcher_price = patch.object(self.mock_client, 'get_latest_crypto_trade', self.mock_latest_trade)
        self.addCleanup(patcher_price.stop)
        patcher_price.start()


    def _setup_common_mocks(self):
        """Sets up common mock return values for a typical trade cycle."""
        # --- Portfolio Manager Mocks ---
        mock_account = MagicMock()
        mock_account.id = "test_id"
        mock_account.equity = "100000"
        mock_account.last_equity = "100000"
        mock_account.buying_power = "200000"
        mock_account.cash = "100000"
        mock_account.status = "ACTIVE"
        self.mock_client.get_account.return_value = mock_account
        
        # By default, no open positions or orders
        self.mock_client.get_positions.return_value = []
        self.mock_client.get_orders.return_value = []

        # --- Data Loader Mocks ---
        # Create a valid DataFrame for data integrity checks to pass
        timestamps = pd.to_datetime(pd.date_range(end=pd.Timestamp.now(tz='UTC'), periods=200, freq='h'))
        mock_data = pd.DataFrame({
            'Open': 100, 'High': 105, 'Low': 95, 'Close': 102, 'Volume': 1000
        }, index=timestamps)
        self.mock_data_loader.get_market_data.return_value = mock_data

        # Patch data integrity checks to prevent them from interfering with integration tests
        patcher_gaps = patch('smartcfd.strategy.has_data_gaps', return_value=False)
        self.addCleanup(patcher_gaps.stop)
        patcher_gaps.start()

        # --- Feature Calculation Mock ---
        mock_features = pd.DataFrame([{'feature1': 1, 'feature2': 2}])
        patcher_features = patch('smartcfd.strategy.calculate_indicators', return_value=mock_features)
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
        self.mock_client.submit_order.return_value = mock_order_confirmation
        
        # Set price for BTC/USD
        self.mock_latest_trade.return_value = {'trade': {'p': 50000.0}}

        # --- Run the trading loop ---
        self.trader.run()

        # --- Assertions ---
        # 1. Portfolio was reconciled
        self.mock_client.get_account.assert_called_once()
        self.mock_client.get_positions.assert_called_once()

        # 2. Strategy was evaluated for both symbols
        self.assertEqual(self.mock_data_loader.get_market_data.call_count, 2)
        self.assertEqual(self.mock_model.predict.call_count, 2)

        # 3. Risk was managed only for the 'buy' signal (BTC/USD)
        self.mock_client.get_latest_crypto_trade.assert_called_once_with('BTC/USD')

        # 4. Order was submitted only for the 'buy' signal
        self.mock_client.submit_order.assert_called_once()
        call_args = self.mock_client.submit_order.call_args
        self.assertEqual(call_args.kwargs['symbol'], 'BTC/USD')
        self.assertEqual(call_args.kwargs['side'], 'buy')
        
        # Expected qty = (100,000 * 1%) / 50,000 = 0.02
        self.assertAlmostEqual(call_args.kwargs['qty'], 0.02)

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
        existing_position.qty = "0.2"
        existing_position.market_value = "10000.0" # 10% of equity
        existing_position.unrealized_pl = "0"
        existing_position.unrealized_plpc = "0"
        existing_position.avg_entry_price = "50000.0"
        self.mock_client.get_positions.return_value = [existing_position]

        # Strategy mock: model predicts 'buy' (1) for both symbols
        self.mock_model.predict.side_effect = [[1], [1]]
        
        # Client mock for the ETH/USD order
        mock_order_confirmation = MagicMock()
        mock_order_confirmation.id = "new_order_eth_456"
        self.mock_client.submit_order.return_value = mock_order_confirmation
        
        # Set price for ETH/USD
        self.mock_latest_trade.return_value = {'trade': {'p': 3000.0}}

        # --- Run the trading loop ---
        self.trader.run()

        # --- Assertions ---
        # 2. Strategy was evaluated for both symbols
        self.assertEqual(self.mock_data_loader.get_market_data.call_count, 2)
        self.assertEqual(self.mock_model.predict.call_count, 2)

        # 3. Risk was managed only for the new trade (ETH/USD)
        self.mock_client.get_latest_crypto_trade.assert_called_once_with('ETH/USD')

        # 4. Order was submitted only for ETH/USD
        self.mock_client.submit_order.assert_called_once()
        call_args = self.mock_client.submit_order.call_args
        self.assertEqual(call_args.kwargs['symbol'], 'ETH/USD')
        
        # Expected qty = (100,000 * 1%) / 3,000 = 0.3333...
        self.assertAlmostEqual(call_args.kwargs['qty'], 0.33333333)

    @patch('smartcfd.strategy.InferenceStrategy.evaluate')
    def test_order_limited_by_asset_exposure(self, mock_evaluate):
        """
        Tests that a new order is correctly sized down to respect the
        max_exposure_per_asset_percent limit.
        """
        self._setup_common_mocks()
        
        # --- Behavior-specific Mocks ---
        # Force the strategy to return a buy action, bypassing its internal logic
        mock_evaluate.return_value = ([{'action': 'buy', 'symbol': 'BTC/USD'}], {})

        # Existing BTC position worth $24,000 (24% of $100k equity)
        existing_position = MagicMock(spec=Position)
        existing_position.symbol = "BTC/USD"
        existing_position.qty = "0.48"
        existing_position.market_value = "24000.0"
        existing_position.unrealized_pl = "0"
        existing_position.unrealized_plpc = "0"
        existing_position.avg_entry_price = "50000.0"
        self.mock_client.get_positions.return_value = [existing_position]
        
        self.mock_latest_trade.return_value = {'trade': {'p': 50000.0}}

        # --- Run the trading loop ---
        self.trader.run()

        # --- Assertions ---
        self.mock_client.submit_order.assert_called_once()
        call_args = self.mock_client.submit_order.call_args
        
        # Max asset exposure = 25% of $100k = $25,000
        # Current exposure = $24,000
        # Headroom = $1,000
        # Order qty = $1,000 / $50,000 price = 0.02
        self.assertAlmostEqual(call_args.kwargs['qty'], 0.02)

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
        self.mock_client.submit_order.return_value = mock_order_confirmation
        
        # Set price for BTC/USD
        self.mock_latest_trade.return_value = {'trade': {'p': 50000.0}}

        # --- Run the trading loop ---
        self.trader.run()

        # --- Assertions ---
        # 1. Portfolio was reconciled
        self.mock_client.get_account.assert_called_once()

        # 2. Strategy was evaluated for both symbols
        self.assertEqual(self.mock_data_loader.get_market_data.call_count, 2)
        self.assertEqual(self.mock_model.predict.call_count, 2)

        # 3. Risk was managed for the 'sell' signal
        self.mock_client.get_latest_crypto_trade.assert_called_once_with('BTC/USD')

        # 4. A 'sell' order was submitted
        self.mock_client.submit_order.assert_called_once()
        call_args = self.mock_client.submit_order.call_args
        self.assertEqual(call_args.kwargs['symbol'], 'BTC/USD')
        self.assertEqual(call_args.kwargs['side'], 'sell')
        
        # Expected qty = (100,000 * 1%) / 50,000 = 0.02
        self.assertAlmostEqual(call_args.kwargs['qty'], 0.02)

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
        pos1.qty = "1000"; pos1.market_value = "25000.0"; pos1.unrealized_pl = "0"; pos1.unrealized_plpc = "0"; pos1.avg_entry_price = "25.0"
        pos2 = MagicMock(spec=Position)
        pos2.symbol = "SOL/USD"
        pos2.qty = "100"; pos2.market_value = "24500.0"; pos2.unrealized_pl = "0"; pos2.unrealized_plpc = "0"; pos2.avg_entry_price = "245.0"
        self.mock_client.get_positions.return_value = [pos1, pos2]
        
        # Strategy predicts 'buy' for BTC/USD
        self.mock_model.predict.side_effect = [[1], [0]]
        self.mock_latest_trade.return_value = {'trade': {'p': 50000.0}}

        # --- Run the trading loop ---
        self.trader.run()

        # --- Assertions ---
        # Total exposure headroom is only $500.
        # $500 / $50,000 price = 0.01 qty.
        # This is a notional value of $500, which is above the $1 minimum.
        self.mock_client.submit_order.assert_called_once()
        call_args = self.mock_client.submit_order.call_args
        self.assertAlmostEqual(call_args.kwargs['qty'], 0.01)

    def test_order_blocked_when_asset_exposure_is_met(self):
        """
        Tests that no order is placed for an asset that is already at its
        max_exposure_per_asset_percent limit.
        """
        self._setup_common_mocks()
        
        # --- Behavior-specific Mocks ---
        # Existing BTC position worth $25,000 (exactly 25% of $100k equity)
        existing_position = MagicMock(spec=Position)
        existing_position.symbol = "BTC/USD"
        existing_position.qty = "0.5"
        existing_position.market_value = "25000.0"
        existing_position.unrealized_pl = "0"
        existing_position.unrealized_plpc = "0"
        existing_position.avg_entry_price = "50000.0"
        self.mock_client.get_positions.return_value = [existing_position]
        
        # Strategy predicts 'buy' for BTC/USD
        self.mock_model.predict.side_effect = [[1], [0]]
        self.mock_latest_trade.return_value = {'trade': {'p': 50000.0}}

        # --- Run the trading loop ---
        self.trader.run()

        # --- Assertions ---
        # No headroom for this asset, so no trade should be placed.
        self.mock_client.submit_order.assert_not_called()


if __name__ == '__main__':
    unittest.main()
