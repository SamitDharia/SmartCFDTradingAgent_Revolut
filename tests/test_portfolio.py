import unittest
from unittest.mock import MagicMock, PropertyMock
import pandas as pd

from smartcfd.portfolio import PortfolioManager, Account, Position

class TestPortfolioManager(unittest.TestCase):
    def setUp(self):
        """Set up a mock Alpaca client and a PortfolioManager instance."""
        self.mock_client = MagicMock()
        self.portfolio_manager = PortfolioManager(self.mock_client)

    def test_initial_state(self):
        """Test that the portfolio manager initializes with an empty state."""
        self.assertIsNone(self.portfolio_manager.account)
        self.assertEqual(self.portfolio_manager.positions, {})
        self.assertEqual(self.portfolio_manager.orders, [])

    def test_reconcile_successful(self):
        """Test a successful reconciliation of account and position data."""
        # Mock the return values from the Alpaca client
        # PortfolioManager expects get_account_info() which can return object-like
        mock_account = MagicMock()
        mock_account.id = "test_account_id"
        mock_account.equity = 100000.0
        mock_account.last_equity = 99000.0
        mock_account.buying_power = 50000.0
        mock_account.cash = 50000.0
        mock_account.status = "ACTIVE"

        mock_position_data = [
            {
                "symbol": "BTC/USD",
                "qty": "1.5",
                "market_value": "60000",
                "unrealized_pl": "1500",
                "unrealized_plpc": "0.025",
                "avg_entry_price": "39000",
                "side": "long"
            },
            {
                "symbol": "ETH/USD",
                "qty": "10",
                "market_value": "30000",
                "unrealized_pl": "-500",
                "unrealized_plpc": "-0.016",
                "avg_entry_price": "3050",
                "side": "long"
            }
        ]
        mock_positions = [MagicMock(**p_data) for p_data in mock_position_data]

        self.mock_client.get_account_info.return_value = mock_account
        self.mock_client.list_positions.return_value = mock_positions
        self.mock_client.get_orders.return_value = [] # No open orders

        # Run reconcile
        self.portfolio_manager.reconcile()

        # Assertions
        self.assertIsNotNone(self.portfolio_manager.account)
        
        # Check account
        self.assertIsInstance(self.portfolio_manager.account, Account)
        self.assertEqual(self.portfolio_manager.account.equity, 100000.0)
        
        # Check positions
        self.assertEqual(len(self.portfolio_manager.positions), 2)
        self.assertIn("BTC/USD", self.portfolio_manager.positions)
        self.assertIn("ETH/USD", self.portfolio_manager.positions)
        
        btc_pos = self.portfolio_manager.positions["BTC/USD"]
        self.assertIsInstance(btc_pos, Position)
        self.assertEqual(btc_pos.qty, 1.5)
        self.assertEqual(btc_pos.market_value, 60000)

    def test_reconcile_get_account_fails(self):
        """Test that the state remains unchanged if getting the account fails."""
        # Setup initial state
        self.portfolio_manager.account = Account(id="old_id", equity=1.0, last_equity=1.0, buying_power=1.0, cash=1.0, status="ACTIVE")
        
        # Mock client failure
        self.mock_client.get_account_info.side_effect = Exception("API Error")
        self.mock_client.list_positions.return_value = [] # Assume this still runs

        # Run reconcile
        self.portfolio_manager.reconcile()

        # The account should NOT be wiped, but marked as offline
        self.assertIsNotNone(self.portfolio_manager.account)
        self.assertFalse(self.portfolio_manager.account.is_online)
        # Positions should be cleared as the call returned an empty list
        self.assertEqual(self.portfolio_manager.positions, {})

    def test_reconcile_get_positions_fails(self):
        """Test that the state remains unchanged if getting positions fails."""
        # Setup initial state
        initial_position = Position(symbol="SPY", qty=10, market_value=5000, unrealized_pl=100, unrealized_plpc=0.02, avg_entry_price=490, side="long")
        self.portfolio_manager.positions = {"SPY": initial_position}
        
        # Mock client calls
        mock_account = MagicMock()
        mock_account.id = "test_id"
        mock_account.equity = 1000.0
        mock_account.last_equity = 1000.0
        mock_account.buying_power = 1000.0
        mock_account.cash = 1000.0
        mock_account.status = "ACTIVE"

        self.mock_client.get_account_info.return_value = mock_account
        self.mock_client.list_positions.side_effect = Exception("API Error")

        # Run reconcile
        self.portfolio_manager.reconcile()

        # Account should be updated
        self.assertIsNotNone(self.portfolio_manager.account)
        self.assertEqual(self.portfolio_manager.account.id, "test_id")
        # Positions should NOT be cleared on failure, they should remain as they were
        self.assertEqual(len(self.portfolio_manager.positions), 1)
        self.assertIn("SPY", self.portfolio_manager.positions)

if __name__ == '__main__':
    unittest.main()
