"""
Verifies the actual orders placed in the Alpaca paper trading account.

This script connects to the Alpaca API and fetches the list of all orders
to compare against the locally logged trade tickets. This helps to confirm
which trades were successfully executed versus which ones failed.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from smartcfd.alpaca_client import get_alpaca_client

# Define API URLs directly in the script for robustness
ALPACA_PAPER_BASE_URL = "https://paper-api.alpaca.markets"
ALPACA_LIVE_BASE_URL = "https://api.alpaca.markets"


def get_api_base_url() -> str:
    """Determines the Alpaca API base URL from environment variables."""
    env = os.getenv("ALPACA_ENV", "paper").lower()
    if env == "live":
        return ALPACA_LIVE_BASE_URL
    return ALPACA_PAPER_BASE_URL


def main():
    """Fetches and displays all orders from the Alpaca account."""
    print("--- Verifying Alpaca Paper Trading Orders ---")
    
    # Load environment variables (.env file), overriding any existing system variables
    load_dotenv(override=True)

    # Get Alpaca configuration
    try:
        api_base_url = get_api_base_url()
        client = get_alpaca_client(api_base=api_base_url)
    except Exception as e:
        print(f"Error initializing Alpaca client: {e}")
        print("Please ensure your API keys are set correctly in the .env file.")
        sys.exit(1)

    try:
        print("Fetching orders from Alpaca...")
        orders = client.get_orders(status="all", limit=500)  # Fetch up to 500 orders

        if not orders:
            print("\nNo orders found in your Alpaca paper trading account.")
            print("This confirms that the 18 trades in the digest were not executed.")
            return

        print(f"\nFound {len(orders)} order(s) in your Alpaca account:")
        print("=" * 80)
        print(f"{'Timestamp (UTC)':<28} {'Symbol':<10} {'Side':<5} {'Qty':<10} {'Status':<10}")
        print("-" * 80)

        for order in sorted(orders, key=lambda o: o.submitted_at, reverse=True):
            ts = order.submitted_at
            symbol = order.symbol
            side = order.side
            qty = order.qty
            status = order.status
            print(f"{ts:<28} {symbol:<10} {side:<5} {qty:<10} {status:<10}")
        
        print("=" * 80)
        print("\nThis list represents the ground truth of what was executed by Alpaca.")

    except Exception as e:
        print(f"\nAn error occurred while fetching orders from Alpaca: {e}")
        print("This could be due to incorrect API keys or a network issue.")
        sys.exit(1)


if __name__ == "__main__":
    main()
