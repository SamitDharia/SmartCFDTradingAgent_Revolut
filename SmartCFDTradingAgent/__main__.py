from __future__ import annotations

import os
import logging

if os.getenv("SKIP_SSL_VERIFY") == "1":
    import SmartCFDTradingAgent.utils.no_ssl  # noqa: F401

import click
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from SmartCFDTradingAgent.data_loader import fetch_and_cache_data
from SmartCFDTradingAgent.indicators import process_all_symbols
from SmartCFDTradingAgent.train_model import train_model
from SmartCFDTradingAgent.backtester import Backtester
from SmartCFDTradingAgent.reporting import generate_html_report
from smartcfd.logging_setup import setup_logging
import pandas as pd
from pathlib import Path

# Setup basic logging for the CLI
setup_logging("INFO")
log = logging.getLogger(__name__)

@click.group()
def cli():
    """Smart CFD Trading Agent CLI."""
    pass

@cli.command()
@click.option("--symbols", "-s", multiple=True, required=True, help="One or more stock symbols to fetch.")
@click.option("--start-date", "-S", required=True, help="Start date in YYYY-MM-DD format.")
@click.option("--end-date", "-E", required=True, help="End date in YYYY-MM-DD format.")
@click.option("--timeframe", "-t", default="minute", type=click.Choice(["minute", "hour", "day"]), help="Timeframe for the data.")
def build_dataset(symbols: list[str], start_date: str, end_date: str, timeframe: str):
    """
    Fetches historical market data from Alpaca and caches it locally in a Parquet file.
    """
    log.info(f"Building dataset for symbols: {', '.join(symbols)}")
    
    tf_map = {
        "minute": TimeFrame.Minute,
        "hour": TimeFrame.Hour,
        "day": TimeFrame(1, TimeFrameUnit.Day) # Assuming 1Day, adjust if needed
    }
    
    try:
        result_path = fetch_and_cache_data(
            symbols=list(symbols),
            start_date=start_date,
            end_date=end_date,
            timeframe=tf_map[timeframe]
        )
        if result_path:
            click.echo(f"Successfully created dataset: {result_path}")
        else:
            click.echo("Failed to create dataset. Check logs for details.", err=True)
    except Exception as e:
        log.error(f"An error occurred during dataset creation: {e}", exc_info=True)
        raise click.ClickException(f"An error occurred: {e}")

@cli.command()
@click.argument("input_file", type=click.Path(exists=True, dir_okay=False))
def engineer_features(input_file: str):
    """
    Loads a dataset from a Parquet file, engineers features, and saves the new dataset.
    """
    log.info(f"Loading dataset from {input_file}")
    try:
        df = pd.read_parquet(input_file)
    except Exception as e:
        raise click.ClickException(f"Failed to read Parquet file: {e}")

    # The data loader now includes a timestamp column, which we'll set as the index
    if 'timestamp' in df.columns:
        df = df.set_index('timestamp')
    else:
        raise click.ClickException("Input file must contain a 'timestamp' column.")

    featured_df = process_all_symbols(df)

    # Create a new filename for the featured dataset
    input_path = Path(input_file)
    output_file = input_path.parent / f"{input_path.stem}_featured.parquet"

    try:
        featured_df.to_parquet(output_file)
        click.echo(f"Successfully created featured dataset: {output_file}")
    except Exception as e:
        raise click.ClickException(f"Failed to save featured dataset: {e}")


@cli.command("train-model")
@click.argument("features_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--output-file", "-o", default="storage/models/xgb_model.joblib", help="Path to save the trained model.")
def train_model_cli(features_file: str, output_file: str):
    """
    Trains a model on the engineered features.
    """
    log.info(f"Starting model training with features from {features_file}")
    try:
        train_model(features_path=features_file, model_output_path=output_file)
        click.echo(f"Model training complete. Model saved to {output_file}")
    except Exception as e:
        log.error(f"An error occurred during model training: {e}", exc_info=True)
        raise click.ClickException(f"An error occurred during model training: {e}")


@cli.command()
@click.argument("features_file", type=click.Path(exists=True, dir_okay=False))
@click.option("--model-path", "-m", required=True, type=click.Path(exists=True, dir_okay=False), help="Path to the trained model file.")
@click.option("--initial-cash", "-c", default=10000.0, help="Initial cash for the backtest.")
@click.option("--signal-threshold", "-t", default=0.5, help="Probability threshold for buy signals.")
@click.option("--report-path", "-r", default="reports/backtest_report.html", help="Path to save the HTML report.")
def backtest(features_file: str, model_path: str, initial_cash: float, signal_threshold: float, report_path: str):
    """
    Runs a backtest of the trading strategy.
    """
    log.info("Starting backtest...")
    
    try:
        # Load features data
        features_df = pd.read_parquet(features_file)
        
        # The backtester now expects 'timestamp' as a column
        if 'timestamp' not in features_df.columns:
             if features_df.index.name == 'timestamp':
                 features_df.reset_index(inplace=True)
             else:
                raise click.ClickException("Features file must have a 'timestamp' column or index.")

        # Initialize and run the backtester
        backtester = Backtester(model_path=model_path, initial_cash=initial_cash)
        results = backtester.run(features_df, signal_threshold=signal_threshold)

        # Print summary
        click.echo("\n--- Backtest Results ---")
        click.echo(f"Initial Portfolio Value: ${results['initial_cash']:,.2f}")
        click.echo(f"Final Portfolio Value:   ${results['final_cash']:,.2f}")
        click.echo(f"Total Return:              {results['total_return_pct']:.2f}%")
        click.echo(f"Sharpe Ratio:              {results['sharpe_ratio']:.2f}")
        click.echo(f"Max Drawdown:              {results['max_drawdown_pct']:.2f}%")
        click.echo(f"Win Rate:                  {results['win_rate_pct']:.2f}%")
        click.echo(f"Total Trades:              {results['num_trades']}")
        
        # Ensure output directory exists
        output_dir = Path(report_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save detailed data and the HTML report
        if not results['trades'].empty:
            results['trades'].to_csv(output_dir / "trades.csv", index=False)
        if not results['equity_curve'].empty:
            results['equity_curve'].to_csv(output_dir / "equity_curve.csv", index=False)
        
        generate_html_report(results, report_path)
        click.echo(f"\nSaved HTML report to: {report_path}")
        click.echo(f"Saved detailed CSVs to: {output_dir.resolve()}")

    except Exception as e:
        log.error(f"An error occurred during backtesting: {e}", exc_info=True)
        raise click.ClickException(f"An error occurred during backtesting: {e}")


if __name__ == "__main__":
    cli()
