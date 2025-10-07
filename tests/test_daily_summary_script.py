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
            {"symbol": "BTC-USD", "qty": 0.1, "entry": 50000, "pnl": 100.0},
        )
        self.create_fake_trade(
            "2025-10-07T11-00-00Z_ETH-USD_Buy.json",
            {"symbol": "ETH-USD", "qty": 1.0, "entry": 4000, "pnl": -150.0},
        )
        self.create_fake_trade(
            "2025-10-07T12-00-00Z_BTC-USD_Sell.json",
            {"symbol": "BTC-USD", "qty": 0.05, "entry": 51000, "pnl": 25.0},
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
        json_report_path, text_report_path = generate_summary(
            logs_dir=self.trade_tickets_path,
            reports_dir=TEST_REPORTS_DIR
        )

        # --- Assertions for JSON data ---
        with open(json_report_path, "r") as f:
            summary_data = json.load(f)
        
        self.assertIn("generated_at", summary_data)
        self.assertEqual(summary_data["total_trades"], 3)
        self.assertEqual(summary_data["trades_by_symbol"], {"BTC-USD": 2, "ETH-USD": 1})
        self.assertEqual(summary_data["trades_by_side"], {"buy": 2, "sell": 1})

        # --- Assertions for text report ---
        with open(text_report_path, "r") as f:
            text_report = f.read()

        self.assertIn("Smart CFD Trading Agent - Daily Digest", text_report)
        self.assertIn("Total Trades: 3", text_report)
        self.assertIn("- BTC-USD: 2 trade(s)", text_report)
        self.assertIn("- ETH-USD: 1 trade(s)", text_report)
        self.assertIn("- Buy: 2 trade(s)", text_report)
        self.assertIn("- Sell: 1 trade(s)", text_report)
        self.assertIn("Total Profit/Loss: $-25.00", text_report)
        
        self.assertEqual(summary_data["total_profit_loss"], -25.0)

    def test_no_trades_found(self):
        """
        Test that the summary generation handles the case where no trades are found.
        """
        # Clear the trade tickets directory
        for f in os.listdir(self.trade_tickets_path):
            os.remove(os.path.join(self.trade_tickets_path, f))

        json_report_path, text_report_path = generate_summary(
            logs_dir=self.trade_tickets_path,
            reports_dir=TEST_REPORTS_DIR
        )

        # Assert that no report files were created
        self.assertIsNone(json_report_path)
        self.assertIsNone(text_report_path)

    @mock.patch("scripts.daily_summary.LOG_DIR", os.path.join(TEST_LOG_DIR, "non_existent_dir"))
    def test_generate_summary_no_log_dir(self):
        """Test behavior when the log directory does not exist."""
        summary_data, text_report = generate_summary(
            logs_dir=os.path.join(TEST_LOG_DIR, "non_existent_dir"),
            reports_dir=TEST_REPORTS_DIR
        )
        self.assertIsNone(summary_data)
        self.assertIsNone(text_report)
