"""
A simple Flask web server to display the trading agent's performance dashboard.
"""

import json
from pathlib import Path
from flask import Flask, render_template, jsonify

app = Flask(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
LOGS_DIR = PROJECT_ROOT / "logs" / "trade_tickets"

@app.route('/')
def dashboard():
    """Serves the main dashboard page."""
    return render_template('dashboard.html')

@app.route('/api/summary')
def api_summary():
    """Provides the daily summary data as JSON."""
    summary_path = REPORTS_DIR / "daily_digest.json"
    if not summary_path.exists():
        return jsonify({"error": "Summary report not found."}), 404
    
    with open(summary_path, 'r') as f:
        data = json.load(f)
    return jsonify(data)

@app.route('/api/trades')
def api_trades():
    """Provides a list of all individual trades."""
    if not LOGS_DIR.exists():
        return jsonify({"error": "Trade logs directory not found."}), 404
        
    trades = []
    for trade_file in sorted(LOGS_DIR.glob("*.json"), reverse=True):
        with open(trade_file, 'r') as f:
            try:
                trade_data = json.load(f)
                # Ensure filename info is included
                trade_data['filename'] = trade_file.name
                trades.append(trade_data)
            except json.JSONDecodeError:
                # Handle cases where a file might be empty or corrupted
                continue
    return jsonify(trades)

def run_server():
    """Runs the Flask development server."""
    # Note: In a production environment, use a proper WSGI server like Gunicorn
    app.run(host='0.0.0.0', port=8080, debug=True)

if __name__ == '__main__':
    run_server()
