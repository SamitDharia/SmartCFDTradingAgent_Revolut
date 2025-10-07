"""
Sends the daily digest reports via email.

This script reads the generated daily_digest.txt and daily_digest.json files
and sends them as an email using the configuration specified in the .env file.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to the Python path to allow importing from SmartCFDTradingAgent
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from dotenv import load_dotenv
from SmartCFDTradingAgent.emailer import send_email

# Load environment variables from .env file, overriding system variables
load_dotenv(override=True)

REPORTS_DIR = project_root / "reports"
TEXT_REPORT_PATH = REPORTS_DIR / "daily_digest.txt"
JSON_REPORT_PATH = REPORTS_DIR / "daily_digest.json"


def main():
    """Main function to send the daily digest email."""
    print("--- Sending Daily Digest Email ---")

    if not TEXT_REPORT_PATH.exists():
        print(f"Error: Text report not found at {TEXT_REPORT_PATH}")
        sys.exit(1)

    try:
        # Read the text report for the email body
        with open(TEXT_REPORT_PATH, "r", encoding="utf-8") as f:
            report_content = f.read()

        # Prepare attachments
        attachments = []
        if TEXT_REPORT_PATH.exists():
            attachments.append(TEXT_REPORT_PATH)
        if JSON_REPORT_PATH.exists():
            attachments.append(JSON_REPORT_PATH)

        # Send the email
        subject = f"SmartCFD Trading Digest for {datetime.utcnow().strftime('%Y-%m-%d')}"
        
        print("Connecting to SMTP server to send email...")
        success = send_email(
            subject=subject,
            body_text=report_content,
            attachments=attachments
        )

        if success:
            print("Successfully sent daily digest email.")
        else:
            # This case might happen if DIGEST_EMAILS is not set
            print("Email not sent. No recipients configured.")

    except RuntimeError as e:
        print(f"Error sending email: {e}")
        print("Please ensure your SMTP settings in the .env file are correct.")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
