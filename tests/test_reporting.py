import pytest
from pathlib import Path
import pandas as pd
from SmartCFDTradingAgent.reporting import generate_html_report


@pytest.fixture
def dummy_backtest_results():
    """Creates a dummy backtest results dictionary for testing."""
    equity_curve = pd.DataFrame({
        "timestamp": pd.to_datetime(pd.date_range(start="2023-01-01", periods=5)),
        "equity": [10000, 10100, 10050, 10200, 10150]
    })
    trades = pd.DataFrame({
        "symbol": ["AAPL", "AAPL"],
        "side": ["buy", "sell"],
        "price": [150, 152],
        "qty": [10, 10]
    })
    results = {
        "initial_cash": 10000.0,
        "final_cash": 10150.0,
        "total_return_pct": 1.5,
        "sharpe_ratio": 1.2,
        "max_drawdown_pct": -0.49,
        "win_rate_pct": 100.0,
        "num_trades": 1,
        "equity_curve": equity_curve,
        "trades": trades
    }
    return results


def test_generate_html_report(dummy_backtest_results, tmp_path):
    """Test that the HTML report is generated correctly."""
    # 1. Setup
    output_file = tmp_path / "report.html"

    # 2. Action
    generate_html_report(dummy_backtest_results, str(output_file))

    # 3. Assert
    # Check if file was created
    assert output_file.exists()

    # Check if file has content
    content = output_file.read_text()
    assert len(content) > 0

    # Check for key pieces of information
    assert "<title>Backtest Report</title>" in content
    assert "<h1>Backtest Performance Report</h1>" in content
    assert "<td>Total Return</td><td>1.50%</td>" in content
    assert "<td>Sharpe Ratio</td><td>1.20</td>" in content
    assert "<td>Max Drawdown</td><td>-0.49%</td>" in content
    assert "<td>Win Rate</td><td>100.00%</td>" in content
    assert "<td>1</td>" in content  # Number of trades
    # Check for the Plotly CDN script, which is a more reliable indicator
    assert "Plotly.newPlot" in content
