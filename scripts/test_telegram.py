#!/usr/bin/env python3
"""Send a quick Telegram test message using credentials from `.env`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from SmartCFDTradingAgent.utils.telegram import send


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a Telegram test ping")
    parser.add_argument(
        "--message",
        default="SmartCFDTradingAgent connectivity test",
        help="Text to send",
    )
    args = parser.parse_args()

    load_dotenv()

    if send(args.message):
        print("Telegram message sent. Check your chat for confirmation.")
        return 0

    print(
        "Failed to send Telegram message. Verify TELEGRAM_BOT_TOKEN and "
        "TELEGRAM_CHAT_ID in your .env file.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
