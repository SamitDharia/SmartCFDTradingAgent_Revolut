import unittest
from unittest.mock import MagicMock

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
        qty = self.risk_manager.calculate_order_qty("BTC/USD", "buy")
        # Expected: (100,000 * 1%) / 50,000 = 0.02
        self.assertAlmostEqual(qty, 0.02)

    def test_qty_limited_by_asset_exposure(self):
        """Order size should be capped by the max_exposure_per_asset_percent."""
        # Existing position worth $24,000 (24% of equity), leaving $1,000 (1%) headroom.
        self.portfolio_manager.positions = {
            "BTC/USD": Position(symbol="BTC/USD", market_value=24000.0, qty=0.48, avg_entry_price=50000.0, unrealized_pl=0, unrealized_plpc=0)
        }
        qty = self.risk_manager.calculate_order_qty("BTC/USD", "buy")
        # Risk per trade is 1% ($1000), asset headroom is 1% ($1000). Min is $1000.
        # Expected: 1000 / 50000 = 0.02
        self.assertAlmostEqual(qty, 0.02)

    def test_qty_limited_by_total_exposure(self):
        """Order size should be capped by the max_total_exposure_percent."""
        # Existing positions worth $49,500 (49.5% of equity), leaving $500 (0.5%) headroom.
        self.portfolio_manager.positions = {
            "ETH/USD": Position(symbol="ETH/USD", market_value=49500.0, qty=16.5, avg_entry_price=3000.0, unrealized_pl=0, unrealized_plpc=0)
        }
        qty = self.risk_manager.calculate_order_qty("BTC/USD", "buy")
        # Risk per trade is 1% ($1000), total headroom is 0.5% ($500). Min is $500.
        # Expected: 500 / 50000 = 0.01
        self.assertAlmostEqual(qty, 0.01)

    def test_qty_is_zero_when_asset_limit_is_met(self):
        """Order size should be zero if the asset exposure limit is already met."""
        # Existing position worth $25,000 (25% of equity), leaving no headroom.
        self.portfolio_manager.positions = {
            "BTC/USD": Position(symbol="BTC/USD", market_value=25000.0, qty=0.5, avg_entry_price=50000.0, unrealized_pl=0, unrealized_plpc=0)
        }
        qty = self.risk_manager.calculate_order_qty("BTC/USD", "buy")
        self.assertEqual(qty, 0)

if __name__ == '__main__':
    unittest.main()
