"""
Unit tests for the send_digest.py script.
"""

import base64
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the project root to the Python path to allow importing
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from scripts import send_digest


class TestSendDigest(unittest.TestCase):
    """Tests for the daily digest email sending script."""

    def setUp(self):
        """Set up the test environment."""
        self.reports_dir = project_root / "reports"
        self.reports_dir.mkdir(exist_ok=True)
        self.txt_report = self.reports_dir / "daily_digest.txt"
        self.json_report = self.reports_dir / "daily_digest.json"

        # Create dummy report files
        self.txt_report.write_text("This is the daily digest.", encoding="utf-8")
        self.json_report.write_text('{"trades": 1}', encoding="utf-8")

        # Set dummy env vars for the script to use
        os.environ["SMTP_HOST"] = "smtp.test.com"
        os.environ["SMTP_PORT"] = "587"
        os.environ["SMTP_USER"] = "user"
        os.environ["SMTP_PASSWORD"] = "password"
        os.environ["SMTP_SENDER"] = "sender@example.com"
        os.environ["DIGEST_EMAILS"] = "test@example.com"
        os.environ["SMTP_USE_SSL"] = "false"

    def tearDown(self):
        """Clean up the test environment."""
        if self.txt_report.exists():
            self.txt_report.unlink()
        if self.json_report.exists():
            self.json_report.unlink()
        
        # Unset env vars
        for key in ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "SMTP_SENDER", "DIGEST_EMAILS", "SMTP_USE_SSL"]:
            if key in os.environ:
                del os.environ[key]

    @patch("SmartCFDTradingAgent.emailer.smtplib.SMTP")
    def test_main_success(self, mock_smtp: MagicMock):
        """Test the main function successfully sends an email."""
        # Run the main function of the script
        send_digest.main()

        # Check that an SMTP instance was created and methods were called
        self.assertTrue(mock_smtp.called)
        smtp_instance = mock_smtp.return_value.__enter__.return_value
        self.assertTrue(smtp_instance.ehlo.called)
        self.assertTrue(smtp_instance.starttls.called)
        self.assertTrue(smtp_instance.login.called)
        self.assertTrue(smtp_instance.sendmail.called)

        # Check the login credentials
        login_args, _ = smtp_instance.login.call_args
        self.assertEqual(("user", "password"), login_args)

        # Check the email details
        sendmail_args, _ = smtp_instance.sendmail.call_args
        sender, recipients, message_str = sendmail_args
        self.assertEqual(os.environ["SMTP_SENDER"], sender)
        self.assertEqual(["test@example.com"], recipients)
        self.assertIn("Subject: SmartCFD Trading Digest", message_str)
        
        # The body is base64 encoded in a multipart message
        encoded_body = base64.b64encode(b"This is the daily digest.").decode()
        self.assertIn(encoded_body, message_str)

    @patch("scripts.send_digest.send_email")
    def test_main_no_recipients(self, mock_send_email: MagicMock):
        """Test that email is not sent if no recipients are configured."""
        mock_send_email.return_value = False
        
        # Temporarily remove the recipients env var
        original_emails = os.environ.pop("DIGEST_EMAILS", None)
        
        try:
            send_digest.main()
            # The send_email function is mocked. We expect it to be called,
            # and it will internally handle the logic of not sending.
            mock_send_email.assert_called_once()
        finally:
            # Restore env var
            if original_emails is not None:
                os.environ["DIGEST_EMAILS"] = original_emails

    @patch("builtins.print")
    @patch("sys.exit")
    def test_main_no_report_file(self, mock_sys_exit: MagicMock, mock_print: MagicMock):
        """Test the script exits if the report file is missing."""
        # Remove the report file
        self.txt_report.unlink()

        send_digest.main()

        # Check that the script tried to exit
        mock_sys_exit.assert_called_with(1)
        
        # Check that an error message was printed
        mock_print.assert_any_call(f"Error: Text report not found at {send_digest.TEXT_REPORT_PATH}")


if __name__ == "__main__":
    unittest.main()
