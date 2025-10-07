"""
This script will house the new backtesting engine.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import argparse
import logging
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

from smartcfd.data_loader import DataLoader
from smartcfd.config import load_config, load_risk_config
from smartcfd.alpaca import build_api_base
from smartcfd.strategy import InferenceStrategy
from smartcfd.risk import RiskManager, BacktestRiskManager
from smartcfd.backtest_broker import MockBroker
from smartcfd.backtest_portfolio import BacktestPortfolio

def setup_logging(level="INFO"):
    """Sets up basic logging."""
    logging.basicConfig(level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def run_backtest(symbol: str, start_date: str, end_date: str, initial_capital: float):
    """
    Main logic for running the backtest.
    """
    log = logging.getLogger("backtester")
    log.info(f"Starting backtest for {symbol} from {start_date} to {end_date} with ${initial_capital:,.2f}")

    cfg = load_config()
    api_base = build_api_base(cfg.alpaca_env)
    data_loader = DataLoader(api_base)

    # 1. Load Data
    log.info("Loading historical data...")
    # Note: The existing DataLoader is designed for fetching recent data for live trading.
    # We may need to adapt it or use a different method for fetching long historical periods.
    # For now, we'll assume it can be adapted.
    try:
        # This is a conceptual placeholder. We'll need to implement fetching a date range.
        data = data_loader.fetch_historical_range(symbol, start_date, end_date, "1Hour") # Assuming 1Hour for now
        if data.empty:
            log.error("No data loaded, cannot run backtest.")
            return
        log.info(f"Loaded {len(data)} data points for {symbol}.")
    except Exception as e:
        log.error(f"Failed to load historical data: {e}")
        return

    # Pre-calculate all features for the entire dataset
    log.info("Pre-calculating features for the entire dataset...")
    from smartcfd.indicators import create_features
    featured_data = create_features(data)
    log.info("Feature calculation complete.")

    # 2. Initialize Components
    log.info("Initializing backtest components...")
    risk_cfg = load_risk_config()
    broker = MockBroker(data)
    portfolio = BacktestPortfolio(initial_capital=initial_capital)
    risk_manager = BacktestRiskManager(risk_cfg)
    strategy = InferenceStrategy()

    log.info("Starting simulation loop...")
    
    equity_curve = []
    
    for i in range(1, len(featured_data)):
        # Set the current time step for the broker
        broker.set_step(i)

        # The data available for making a decision at step `i` is everything up to `i`.
        current_feature_row = featured_data.iloc[[i]]
        
        # 4. Evaluate strategy
        signal = strategy.evaluate_backtest(current_feature_row)

        # 5. Execute trades
        current_price = featured_data['close'].iloc[i]
        if signal["decision"] == "buy":
            qty_to_buy = risk_manager.calculate_order_qty(symbol, current_price, portfolio)
            if qty_to_buy > 0:
                order = broker.submit_order(symbol, qty_to_buy, "buy", "market", "gtc")
                if order and order.filled_avg_price:
                    portfolio.execute_order(symbol, order.qty, order.side, order.filled_avg_price)
        elif signal["decision"] == "sell":
            current_position = portfolio.positions.get(symbol, 0)
            if current_position > 0:
                order = broker.submit_order(symbol, current_position, "sell", "market", "gtc")
                if order and order.filled_avg_price:
                    portfolio.execute_order(symbol, order.qty, order.side, order.filled_avg_price)

        # 6. Update portfolio equity
        portfolio.update_equity({symbol: current_price})
        equity_curve.append(portfolio.get_total_equity({symbol: current_price}))

    log.info("Simulation finished. Calculating performance...")

    # --- Performance Calculation ---
    returns = pd.Series(equity_curve).pct_change().dropna()
    sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0 # Annualized
    
    equity_series = pd.Series(equity_curve)
    roll_max = equity_series.cummax()
    daily_drawdown = equity_series/roll_max - 1.0
    max_drawdown = daily_drawdown.min()

    total_trades = broker.get_trade_count()
    
    # --- Final Results ---
    log.info("--- Backtest Results ---")
    log.info(f"Initial Capital: ${initial_capital:,.2f}")
    final_equity = portfolio.get_total_equity({symbol: data['close'].iloc[-1]})
    log.info(f"Final Equity:    ${final_equity:,.2f}")
    log.info(f"Total Return:    {((final_equity - initial_capital) / initial_capital) * 100:.2f}%")
    log.info(f"Sharpe Ratio:    {sharpe_ratio:.2f}")
    log.info(f"Max Drawdown:    {max_drawdown:.2%}")
    log.info(f"Total Trades:    {total_trades}")
    log.info("------------------------")

    # --- Generate Equity Curve Plot ---
    plt.figure(figsize=(12, 6))
    plt.plot(equity_series)
    plt.title(f'Equity Curve for {symbol}')
    plt.xlabel('Time Steps')
    plt.ylabel('Equity (USD)')
    plot_filename = f"reports/backtest_{symbol.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    plt.savefig(plot_filename)
    log.info(f"Equity curve plot saved to {plot_filename}")

    # --- Save Trade History ---
    trade_history_df = broker.get_trade_history()
    if not trade_history_df.empty:
        trade_filename = f"reports/trade_history_{symbol.replace('/', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        trade_history_df.to_csv(trade_filename, index=False)
        log.info(f"Trade history saved to {trade_filename}")


def main():
    """
    Main function to run the backtesting engine.
    """
    setup_logging()
    log = logging.getLogger("backtester")
    log.info("Backtesting engine starting...")

    parser = argparse.ArgumentParser(description="SmartCFD Backtesting Engine")
    parser.add_argument("--symbol", type=str, required=True, help="The symbol to backtest (e.g., 'BTC/USD')")
    parser.add_argument("--start", type=str, required=True, help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end", type=str, required=True, help="End date in YYYY-MM-DD format")
    parser.add_argument("--capital", type=float, default=10000.0, help="Initial capital for the backtest")
    args = parser.parse_args()

    run_backtest(args.symbol, args.start, args.end, args.capital)

    log.info("Backtesting engine finished.")

if __name__ == "__main__":
    main()
