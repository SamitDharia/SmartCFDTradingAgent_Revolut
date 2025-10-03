#!/usr/bin/env python3
"""Send a daily trade summary via Telegram."""

from importlib import import_module

from dotenv import load_dotenv

from SmartCFDTradingAgent.utils.trade_logger import aggregate_trade_stats


load_dotenv()


def main() -> None:
    telegram = import_module("SmartCFDTradingAgent.utils.telegram")

    stats = aggregate_trade_stats()
    message = (
        "Daily summary\n"
        f"Wins: {stats['wins']}\n"
        f"Losses: {stats['losses']}\n"
        f"Open trades: {stats['open']}"
    )
    telegram.send(message)


if __name__ == "__main__":
    main()
