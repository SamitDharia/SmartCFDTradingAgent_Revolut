import json
import os
import shutil
from pathlib import Path
from unittest import TestCase, mock

from scripts.send_digest import main as send_digest_main

# Define paths for testing
TEST_SCRIPT_DIR = Path(__file__).resolve().parent
TEST_PROJECT_ROOT = TEST_SCRIPT_DIR.parent
TEST_REPORTS_DIR = TEST_PROJECT_ROOT / "tests" / "temp_test_reports_for_send"


class TestSendDigestScript(TestCase):
    def setUp(self):
        """Set up temporary directories and fake report files."""
        os.makedirs(TEST_REPORTS_DIR, exist_ok=True)
        self.text_report_path = TEST_REPORTS_DIR / "daily_digest.txt"
        self.json_report_path = TEST_REPORTS_DIR / "daily_digest.json"

        # Create a fake text report
        with open(self.text_report_path, "w") as f:
            f.write("This is the plain text report.")

        # Create a fake JSON report with some data
        self.fake_summary_data = {
            "total_profit_loss": 123.45,
            "win_rate_percent": 75.0,
            "total_trades": 4,
            "total_volume": 50000,
            "win_count": 3,
            "loss_count": 1,
            "biggest_winner": 100,
            "biggest_loser": -50,
            "average_gain": 75,
            "average_loss": -50,
            "trades_by_symbol": {"BTC-USD": 4},
            "trades_by_side": {"buy": 2, "sell": 2},
            "trades": [],
        }
        with open(self.json_report_path, "w") as f:
            json.dump(self.fake_summary_data, f)

    def tearDown(self):
        """Clean up the temporary directories."""
        shutil.rmtree(TEST_REPORTS_DIR)

    @mock.patch("scripts.send_digest.send_email")
    @mock.patch("scripts.send_digest.REPORTS_DIR", TEST_REPORTS_DIR)
    def test_send_digest_with_html(self, mock_send_email):
        """
        Test that the main function reads reports, generates HTML,
        and calls send_email with the correct arguments.
        """
        # Run the main function of the script
        send_digest_main()

        # Assert that send_email was called once
        mock_send_email.assert_called_once()

        # Get the arguments passed to send_email
        call_args, call_kwargs = mock_send_email.call_args
        
        # Assertions on the arguments
        self.assertIn("SmartCFD Trading Digest", call_kwargs["subject"])
        self.assertEqual(call_kwargs["body_text"], "This is the plain text report.")
        
        # Check that html_body was generated and is a non-empty string
        html_body = call_kwargs["html_body"]
        self.assertIsInstance(html_body, str)
        self.assertIn("Key Performance Indicators", html_body)
        self.assertIn("$123.45", html_body) # Check for PnL
        self.assertIn("75.00%", html_body) # Check for Win Rate

        # Check attachments
        attachments = call_kwargs["attachments"]
        self.assertIn(self.text_report_path, attachments)
        self.assertIn(self.json_report_path, attachments)

    @mock.patch("scripts.send_digest.send_email")
    @mock.patch("scripts.send_digest.REPORTS_DIR", TEST_REPORTS_DIR)
    @mock.patch("builtins.print")
    def test_main_no_report_file(self, mock_print, mock_send_email):
        """Test the script exits if the report file is missing."""
        # Remove the report file
        os.remove(self.text_report_path)

        # Run the main function and expect a SystemExit
        with self.assertRaises(SystemExit) as cm:
            send_digest_main()

        # Check that the script tried to exit with code 1
        self.assertEqual(cm.exception.code, 1)
        
        # Check that an error message was printed
        mock_print.assert_any_call(f"Error: Text report not found at {self.text_report_path}")
        
        # Ensure email was not sent
        mock_send_email.assert_not_called()
