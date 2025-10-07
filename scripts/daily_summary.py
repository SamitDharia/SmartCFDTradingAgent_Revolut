#!/usr/bin/env python3
"""
Generates a daily summary of trading activity by parsing trade tickets.
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import subprocess

# Define paths relative to the script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
LOG_DIR = os.path.join(PROJECT_ROOT, "logs", "trade_tickets")
REPORT_DIR = os.path.join(PROJECT_ROOT, "reports")
REPORT_TXT_PATH = os.path.join(REPORT_DIR, "daily_digest.txt")
REPORT_JSON_PATH = os.path.join(REPORT_DIR, "daily_digest.json")


def generate_summary(logs_dir: Path, reports_dir: Path) -> tuple[Path, Path]:
    """
    Scans the trade ticket directory, aggregates statistics, and generates reports.

    Args:
        logs_dir (Path): The directory where trade log files are stored.
        reports_dir (Path): The directory where report files will be saved.

    Returns:
        A tuple containing the paths to the generated text and JSON reports.
    """
    if not os.path.exists(logs_dir):
        print(f"Error: Trade ticket log directory not found at {logs_dir}")
        return None, None

    trade_files = [f for f in os.listdir(logs_dir) if f.endswith(".json")]
    
    if not trade_files:
        print("No trades found for today.")
        return None, None

    all_trades = []
    for trade_file in trade_files:
        try:
            with open(os.path.join(logs_dir, trade_file), "r") as f:
                trade_data = json.load(f)
                # The filename contains valuable context not in the JSON
                parts = trade_file.replace(".json", "").split("_")
                trade_data["timestamp"] = parts[0]
                trade_data["filename_symbol"] = parts[1]
                trade_data["filename_side"] = parts[2]
                all_trades.append(trade_data)
        except (json.JSONDecodeError, IndexError) as e:
            print(f"Warning: Could not parse file {trade_file}. Error: {e}")
            continue

    # --- Aggregate Statistics ---
    total_trades = len(all_trades)
    trades_by_symbol = Counter(t["filename_symbol"] for t in all_trades)
    trades_by_side = Counter(t["filename_side"].lower() for t in all_trades)
    total_profit_loss = sum(float(t.get("pnl", 0.0)) for t in all_trades)

    # --- Prepare Reports ---
    summary_data = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_trades": total_trades,
        "trades_by_symbol": dict(trades_by_symbol),
        "trades_by_side": dict(trades_by_side),
        "total_profit_loss": total_profit_loss,
        "trades": all_trades,
    }

    # --- Format Text Report ---
    pnl_color = "green" if total_profit_loss >= 0 else "red"
    pnl_str = f"${total_profit_loss:,.2f}"
    
    report_lines = [
        "Smart CFD Trading Agent - Daily Digest",
        f"Generated on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "=" * 40,
        f"Total Trades: {total_trades}",
        f"Total Profit/Loss: {pnl_str}",
        "\n--- Trades by Symbol ---",
    ]
    for symbol, count in trades_by_symbol.items():
        report_lines.append(f"- {symbol}: {count} trade(s)")

    report_lines.append("\n--- Trades by Side ---")
    for side, count in trades_by_side.items():
        report_lines.append(f"- {side.capitalize()}: {count} trade(s)")
    
    report_lines.append("\n" + "=" * 40)
    report_lines.append("End of Report")

    text_report = "\n".join(report_lines)

    # Ensure the reports directory exists
    os.makedirs(reports_dir, exist_ok=True)

    # Write the JSON report
    json_report_path = os.path.join(reports_dir, "daily_digest.json")
    with open(json_report_path, "w") as f:
        json.dump(summary_data, f, indent=4)
    print(f"Successfully generated JSON digest: {json_report_path}")

    # Write the text report
    text_report_path = os.path.join(reports_dir, "daily_digest.txt")
    with open(text_report_path, "w") as f:
        f.write(text_report)
    print(f"Successfully generated daily digest: {text_report_path}")

    return json_report_path, text_report_path

def main():
    """Main function to generate and print the daily summary."""
    project_root = Path(__file__).resolve().parent.parent
    logs_dir = project_root / "logs" / "trade_tickets"
    reports_dir = project_root / "reports"

    try:
        txt_path, _ = generate_summary(logs_dir, reports_dir)

        # Print the generated report to the console
        print("\n" + "=" * 80)
        print(" " * 30 + "DAILY DIGEST")
        print("=" * 80)
        with open(txt_path, "r", encoding="utf-8") as f:
            print(f.read())
        print("=" * 80)

        # Run the script to send the email digest
        send_script_path = project_root / "scripts" / "send_digest.py"
        if send_script_path.exists():
            print("\n--- Triggering Email Dispatch ---")
            # Use sys.executable to ensure we run with the same python interpreter
            result = subprocess.run(
                [sys.executable, str(send_script_path)],
                capture_output=True,
                text=True,
                check=False  # We will check the result manually
            )
            print(result.stdout)
            if result.returncode != 0:
                print("--- Email Dispatch Failed ---")
                print(result.stderr)
            else:
                print("--- Email Dispatch Finished ---")

    except FileNotFoundError:
        print("Error: Logs directory not found. Please ensure the directory structure is correct.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()
