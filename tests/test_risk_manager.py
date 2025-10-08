import unittest
from unittest.mock import MagicMock
import pandas as pd

from smartcfd.risk import RiskManager
from smartcfd.portfolio import PortfolioManager, Account, Position
from smartcfd.config import RiskConfig

class TestRiskManager(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.portfolio_manager = PortfolioManager(self.mock_client)
        self.risk_config = RiskConfig(
            risk_per_trade_percent=1.0,
            max_total_exposure_percent=50.0,
            max_exposure_per_asset_percent=25.0,
        )
        self.risk_manager = RiskManager(self.portfolio_manager, self.risk_config)

        # Mock account state
        self.portfolio_manager.account = Account(
            id="test_id", equity=100000.0, last_equity=100000.0,
            buying_power=200000.0, cash=100000.0, status="ACTIVE", is_online=True
        )
        
        # Mock price feed
        self.mock_client.get_latest_crypto_trade.return_value = {'trade': {'p': 50000.0}}

    def test_qty_limited_by_risk_per_trade(self):
        """Order size should be determined by risk_per_trade_percent when no other limits are hit."""
        qty, _ = self.risk_manager.calculate_order_qty("BTC/USD", "buy")
        # Expected: (100,000 * 1%) / 50,000 = 0.02
        self.assertAlmostEqual(qty, 0.02)

    def test_qty_limited_by_asset_exposure(self):
        """Order size should be capped by the max_exposure_per_asset_percent."""
        # Existing position worth $24,000 (24% of equity), leaving $1,000 (1%) headroom.
        self.portfolio_manager.positions = {
            "BTC/USD": Position(symbol="BTC/USD", market_value=24000.0, qty=0.48, avg_entry_price=50000.0, unrealized_pl=0, unrealized_plpc=0, side="long")
        }
        qty, _ = self.risk_manager.calculate_order_qty("BTC/USD", "buy")
        # Risk per trade is 1% ($1000), asset headroom is 1% ($1000). Min is $1000.
        # Expected: 1000 / 50000 = 0.02
        self.assertAlmostEqual(qty, 0.02)

    def test_qty_limited_by_total_exposure(self):
        """Order size should be capped by the max_total_exposure_percent."""
        # Existing positions worth $49,500 (49.5% of equity), leaving $500 (0.5%) headroom.
        self.portfolio_manager.positions = {
            "ETH/USD": Position(symbol="ETH/USD", market_value=49500.0, qty=16.5, avg_entry_price=3000.0, unrealized_pl=0, unrealized_plpc=0, side="long")
        }
        qty, _ = self.risk_manager.calculate_order_qty("BTC/USD", "buy")
        # Risk per trade is 1% ($1000), total headroom is 0.5% ($500). Min is $500.
        # Expected: 500 / 50000 = 0.01
        self.assertAlmostEqual(qty, 0.01)

    def test_qty_is_zero_when_asset_limit_is_met(self):
        """Order size should be zero if the asset exposure limit is already met."""
        # Existing position worth $25,000 (25% of equity), leaving no headroom.
        self.portfolio_manager.positions = {
            "BTC/USD": Position(symbol="BTC/USD", market_value=25000.0, qty=0.5, avg_entry_price=50000.0, unrealized_pl=0, unrealized_plpc=0, side="long")
        }
        qty, _ = self.risk_manager.calculate_order_qty("BTC/USD", "buy")
        self.assertEqual(qty, 0)

    def test_generate_bracket_order_for_buy(self):
        """Tests generating a bracket order for a buy."""
        self.risk_manager.config.stop_loss_atr_multiplier = 1.5
        self.risk_manager.config.take_profit_atr_multiplier = 2.0

        historical_data = pd.DataFrame({
            'high': [50100.0] * 15, 'low': [49900.0] * 15, 'close': [50000.0] * 15
        })
        
        # Pass qty as a float, which is what calculate_order_qty returns
        order_data = self.risk_manager.generate_bracket_order("BTC/USD", "buy", 0.02, 50000.0, historical_data)
        
        self.assertIsInstance(order_data.qty, str)
        self.assertAlmostEqual(float(order_data.qty), 0.02)
        self.assertEqual(order_data.side, 'buy')
        self.assertEqual(order_data.order_class, 'bracket')
        
        self.assertAlmostEqual(float(order_data.stop_loss['stop_price']), 49700.0)
        self.assertAlmostEqual(float(order_data.take_profit['limit_price']), 50400.0)

    def test_generate_bracket_order_for_sell(self):
        """Tests generating a bracket order for a short sell."""
        self.risk_manager.config.stop_loss_atr_multiplier = 1.5
        self.risk_manager.config.take_profit_atr_multiplier = 3.0

        historical_data = pd.DataFrame({
            'high': [50100.0] * 15, 'low': [49900.0] * 15, 'close': [50000.0] * 15
        })
        
        # Pass qty as a float
        order_data = self.risk_manager.generate_bracket_order("BTC/USD", "sell", 0.02, 50000.0, historical_data)
        
        self.assertIsInstance(order_data.qty, str)
        self.assertAlmostEqual(float(order_data.qty), 0.02)
        self.assertEqual(order_data.side, 'sell')

        self.assertAlmostEqual(float(order_data.stop_loss['stop_price']), 50300.0)
        self.assertAlmostEqual(float(order_data.take_profit['limit_price']), 49400.0)

if __name__ == '__main__':
    unittest.main()
