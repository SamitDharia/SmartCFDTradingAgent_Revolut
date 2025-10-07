import os
import json
import shutil
from unittest import TestCase, mock

from scripts.daily_summary import generate_summary

# Define paths for testing
TEST_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_PROJECT_ROOT = os.path.dirname(TEST_SCRIPT_DIR)
TEST_LOG_DIR = os.path.join(TEST_PROJECT_ROOT, "tests", "temp_test_logs")
TEST_REPORTS_DIR = os.path.join(TEST_PROJECT_ROOT, "tests", "temp_test_reports")


class TestDailySummaryScript(TestCase):
    def setUp(self):
        """Set up a temporary directory structure for testing."""
        # Create temporary log and report directories
        os.makedirs(os.path.join(TEST_LOG_DIR, "trade_tickets"), exist_ok=True)
        os.makedirs(TEST_REPORTS_DIR, exist_ok=True)

        # Create some fake trade ticket files
        self.trade_tickets_path = os.path.join(TEST_LOG_DIR, "trade_tickets")
        self.create_fake_trade(
            "2025-10-07T10-00-00Z_BTC-USD_Buy.json",
            {"symbol": "BTC-USD", "qty": 0.1, "entry": 50000},
        )
        self.create_fake_trade(
            "2025-10-07T11-00-00Z_ETH-USD_Buy.json",
            {"symbol": "ETH-USD", "qty": 1.0, "entry": 4000},
        )
        self.create_fake_trade(
            "2025-10-07T12-00-00Z_BTC-USD_Sell.json",
            {"symbol": "BTC-USD", "qty": 0.05, "entry": 51000},
        )

    def tearDown(self):
        """Clean up the temporary directories."""
        shutil.rmtree(TEST_LOG_DIR)
        shutil.rmtree(TEST_REPORTS_DIR)

    def create_fake_trade(self, filename, data):
        """Helper to create a single trade ticket file."""
        with open(os.path.join(self.trade_tickets_path, filename), "w") as f:
            json.dump(data, f)

    @mock.patch("scripts.daily_summary.LOG_DIR", os.path.join(TEST_LOG_DIR, "trade_tickets"))
    def test_generate_summary(self):
        """
        Test that the summary generation correctly aggregates stats from fake logs.
        """
        summary_data, text_report = generate_summary()

        # --- Assertions for JSON data ---
        self.assertIn("generated_at", summary_data)
        self.assertEqual(summary_data["total_trades"], 3)
        self.assertEqual(summary_data["trades_by_symbol"]["BTC-USD"], 2)
        self.assertEqual(summary_data["trades_by_symbol"]["ETH-USD"], 1)
        self.assertEqual(summary_data["trades_by_side"]["buy"], 2)
        self.assertEqual(summary_data["trades_by_side"]["sell"], 1)
        self.assertEqual(len(summary_data["trades"]), 3)

        # --- Assertions for Text Report ---
        self.assertIn("Total Trades: 3", text_report)
        self.assertIn("- BTC-USD: 2 trade(s)", text_report)
        self.assertIn("- ETH-USD: 1 trade(s)", text_report)
        self.assertIn("- Buy: 2 trade(s)", text_report)
        self.assertIn("- Sell: 1 trade(s)", text_report)

    @mock.patch("scripts.daily_summary.LOG_DIR", os.path.join(TEST_LOG_DIR, "non_existent_dir"))
    def test_generate_summary_no_log_dir(self):
        """Test behavior when the log directory does not exist."""
        summary_data, text_report = generate_summary()
        self.assertEqual(summary_data, {})
        self.assertIn("Error: Trade ticket log directory not found", text_report)

    @mock.patch("scripts.daily_summary.LOG_DIR", os.path.join(TEST_LOG_DIR, "trade_tickets"))
    def test_generate_summary_no_trades(self):
        """Test behavior when the log directory is empty."""
        # Clear the directory for this test
        for f in os.listdir(self.trade_tickets_path):
            os.remove(os.path.join(self.trade_tickets_path, f))

        summary_data, text_report = generate_summary()
        self.assertEqual(summary_data, {})
        self.assertIn("No trades found for today", text_report)
