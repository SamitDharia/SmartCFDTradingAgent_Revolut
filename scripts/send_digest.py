"""
Sends the daily digest reports via email.

This script reads the generated daily_digest.txt and daily_digest.json files
and sends them as an email using the configuration specified in the .env file.
"""

import os
import sys
import json
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


def generate_html_report(summary_data: dict) -> str:
    """Generates an HTML report from the summary data."""
    # --- CSS Styles ---
    styles = """
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f4f4f4; }
        .container { max-width: 800px; margin: 20px auto; background-color: #ffffff; border: 1px solid #dddddd; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { background-color: #0046be; color: #ffffff; padding: 20px; text-align: center; border-top-left-radius: 8px; border-top-right-radius: 8px; }
        .header h1 { margin: 0; font-size: 24px; }
        .content { padding: 20px; }
        .section { margin-bottom: 20px; }
        .section h2 { font-size: 20px; color: #0046be; border-bottom: 2px solid #eeeeee; padding-bottom: 10px; margin-top: 0; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #dddddd; }
        th { background-color: #f8f8f8; font-weight: bold; }
        .kpi-table td:first-child { font-weight: bold; color: #333; }
        .kpi-table td:last-child { text-align: right; font-family: 'Courier New', Courier, monospace; font-size: 16px; }
        .footer { text-align: center; padding: 15px; font-size: 12px; color: #888888; background-color: #f8f8f8; border-bottom-left-radius: 8px; border-bottom-right-radius: 8px; }
        .win { color: #28a745; }
        .loss { color: #dc3545; }
    </style>
    """

    # --- Helper to format numbers ---
    def format_currency(value):
        return f"${value:,.2f}"

    def format_pnl(value):
        css_class = "win" if value > 0 else "loss" if value < 0 else ""
        return f'<span class="{css_class}">{format_currency(value)}</span>'

    # --- KPI Section ---
    kpis = {
        "Total Profit/Loss": format_pnl(summary_data.get('total_profit_loss', 0)),
        "Win Rate": f"{summary_data.get('win_rate_percent', 0):.2f}%",
        "Total Trades": summary_data.get('total_trades', 0),
        "Total Volume Traded": format_currency(summary_data.get('total_volume', 0)),
        "Wins / Losses": f"{summary_data.get('win_count', 0)} / {summary_data.get('loss_count', 0)}",
        "Biggest Winner": format_pnl(summary_data.get('biggest_winner', 0)),
        "Biggest Loser": format_pnl(summary_data.get('biggest_loser', 0)),
        "Average Gain": format_pnl(summary_data.get('average_gain', 0)),
        "Average Loss": format_pnl(summary_data.get('average_loss', 0)),
    }
    kpi_rows = "".join(f"<tr><td>{key}</td><td>{value}</td></tr>" for key, value in kpis.items())

    # --- Trades by Symbol/Side ---
    symbol_rows = "".join(f"<tr><td>{symbol}</td><td>{count}</td></tr>" for symbol, count in summary_data.get('trades_by_symbol', {}).items())
    side_rows = "".join(f"<tr><td>{side.capitalize()}</td><td>{count}</td></tr>" for side, count in summary_data.get('trades_by_side', {}).items())

    # --- All Trades Table ---
    trade_headers = ["Timestamp", "Symbol", "Side", "Qty", "Entry Price", "Notional", "PnL"]
    trade_header_html = "".join(f"<th>{h}</th>" for h in trade_headers)
    trade_rows = ""
    for trade in summary_data.get('trades', []):
        ts = trade.get('filename_timestamp', '').replace('T', ' ').replace('Z', '')
        trade_rows += f"""
        <tr>
            <td>{ts}</td>
            <td>{trade.get('symbol', 'N/A')}</td>
            <td>{trade.get('filename_side', 'N/A').capitalize()}</td>
            <td>{trade.get('qty', 0)}</td>
            <td>{format_currency(trade.get('entry', 0))}</td>
            <td>{format_currency(trade.get('notional', 0))}</td>
            <td>{format_pnl(trade.get('pnl', 0))}</td>
        </tr>
        """

    # --- Assemble HTML ---
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>SmartCFD Trading Digest</title>
        {styles}
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>SmartCFD Trading Digest</h1>
            </div>
            <div class="content">
                <div class="section">
                    <h2>Key Performance Indicators</h2>
                    <table class="kpi-table">{kpi_rows}</table>
                </div>
                <div class="section">
                    <h2>Breakdown</h2>
                    <table>
                        <tr>
                            <th style="width:50%;">Trades by Symbol</th>
                            <th style="width:50%;">Trades by Side</th>
                        </tr>
                        <tr>
                            <td><table>{symbol_rows}</table></td>
                            <td><table>{side_rows}</table></td>
                        </tr>
                    </table>
                </div>
                <div class="section">
                    <h2>All Trades</h2>
                    <table>
                        <thead><tr>{trade_header_html}</tr></thead>
                        <tbody>{trade_rows}</tbody>
                    </table>
                </div>
            </div>
            <div class="footer">
                Generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}
            </div>
        </div>
    </body>
    </html>
    """
    return html


def main():
    """Main function to send the daily digest email."""
    print("--- Sending Daily Digest Email ---")

    # Define paths inside main to allow for easier mocking in tests
    text_report_path = REPORTS_DIR / "daily_digest.txt"
    json_report_path = REPORTS_DIR / "daily_digest.json"

    if not text_report_path.exists():
        print(f"Error: Text report not found at {text_report_path}")
        sys.exit(1)

    try:
        # Read the text report for the email body
        with open(text_report_path, "r", encoding="utf-8") as f:
            report_content = f.read()

        # Generate HTML report from JSON data
        html_content = None
        if json_report_path.exists():
            with open(json_report_path, "r", encoding="utf-8") as f:
                summary_data = json.load(f)
            html_content = generate_html_report(summary_data)
            print("Successfully generated HTML report.")
        else:
            print("Warning: JSON report not found, cannot generate HTML email body.")


        # Prepare attachments
        attachments = []
        if text_report_path.exists():
            attachments.append(text_report_path)
        if json_report_path.exists():
            attachments.append(json_report_path)

        # Send the email
        subject = f"SmartCFD Trading Digest for {datetime.utcnow().strftime('%Y-%m-%d')}"
        send_email(
            subject=subject,
            body_text=report_content,
            html_body=html_content,
            attachments=attachments,
        )
        print("--- Daily digest email sent successfully! ---")

    except Exception as e:
        print(f"An error occurred while sending the email: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
