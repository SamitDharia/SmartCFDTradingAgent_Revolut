import logging
from pathlib import Path

import joblib
import pandas as pd
import numpy as np

log = logging.getLogger(__name__)


class Backtester:
    """
    A simple event-driven backtester for evaluating a trading strategy.
    """

    def __init__(self, model_path: str, initial_cash: float = 10000.0):
        """
        Initializes the Backtester.

        Args:
            model_path: Path to the trained model file.
            initial_cash: The starting cash for the backtest.
        """
        self.model_path = model_path
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.model = self._load_model()

        self.positions = {}  # { 'symbol': { 'qty': float, 'entry_price': float } }
        self.trades = []  # List of trade dictionaries
        self.equity_curve = []  # List of portfolio values over time

    def _load_model(self):
        """Loads the trained model from the specified path."""
        log.info(f"Loading model from {self.model_path}")
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"Model not found at {self.model_path}")
        return joblib.load(self.model_path)

    def run(self, features_df: pd.DataFrame, signal_threshold: float = 0.5):
        """
        Runs the backtest on the provided historical data.

        Args:
            features_df: DataFrame with engineered features, indexed by timestamp.
            signal_threshold: The probability threshold to trigger a 'buy' signal.
        """
        log.info(f"Starting backtest with initial cash: ${self.initial_cash:,.2f}")

        # Ensure data is sorted by time and symbol
        features_df = features_df.sort_values(by=["timestamp", "symbol"])

        # Get the list of feature names the model was trained on
        model_features = self.model.get_booster().feature_names

        for timestamp, group in features_df.groupby("timestamp"):
            for _, row in group.iterrows():
                current_price = row["close"]
                symbol = row["symbol"]

                # 1. Generate Signal
                # Ensure all required features are present
                if not all(f in row for f in model_features):
                    log.debug(
                        f"Skipping {timestamp} for {symbol} due to missing features."
                    )
                    continue

                features = row[model_features].to_frame().T.astype(float)
                probability = self.model.predict_proba(features)[0][
                    1
                ]  # Probability of class 1 (price up)

                # 2. Execute Strategy
                # Simple strategy: Buy if signal > threshold and not in position. Sell after one bar.
                if symbol not in self.positions and probability > signal_threshold:
                    # Buy signal
                    self._execute_trade(
                        timestamp, symbol, "buy", current_price, 1
                    )  # Buy 1 share
                elif symbol in self.positions:
                    # Sell signal (holding for one bar)
                    self._execute_trade(
                        timestamp, symbol, "sell", current_price, self.positions[symbol]["qty"]
                    )

            # 3. Update Portfolio Equity at the end of each timestamp
            portfolio_value = self._calculate_portfolio_value(group)
            self.equity_curve.append({"timestamp": timestamp, "equity": portfolio_value})

        log.info("Backtest finished.")
        return self.generate_results()

    def _execute_trade(self, timestamp, symbol, side, price, qty):
        """Executes a trade and updates portfolio state."""
        cost = price * qty

        if side == "buy":
            if self.cash >= cost:
                self.cash -= cost
                self.positions[symbol] = {"qty": qty, "entry_price": price}
                self.trades.append(
                    {
                        "timestamp": timestamp,
                        "symbol": symbol,
                        "side": "buy",
                        "qty": qty,
                        "price": price,
                    }
                )
                log.debug(f"{timestamp}: Bought {qty} {symbol} @ ${price:.2f}")
            else:
                log.warning(f"{timestamp}: Insufficient cash to buy {qty} {symbol}.")

        elif side == "sell":
            if symbol in self.positions and self.positions[symbol]["qty"] == qty:
                self.cash += cost
                del self.positions[symbol]
                self.trades.append(
                    {
                        "timestamp": timestamp,
                        "symbol": symbol,
                        "side": "sell",
                        "qty": qty,
                        "price": price,
                    }
                )
                log.debug(f"{timestamp}: Sold {qty} {symbol} @ ${price:.2f}")

    def _calculate_portfolio_value(self, current_data: pd.DataFrame):
        """Calculates the current total value of the portfolio."""
        holdings_value = 0
        for symbol, position in self.positions.items():
            # Get the most recent price for the symbol from the current group of data
            if symbol in current_data["symbol"].values:
                last_price = current_data[current_data["symbol"] == symbol][
                    "close"
                ].iloc[-1]
                holdings_value += position["qty"] * last_price
            else:
                # If symbol not in current data, use entry price (less accurate but a fallback)
                holdings_value += position["qty"] * position["entry_price"]
        return self.cash + holdings_value

    def generate_results(self):
        """Generates a summary of the backtest results."""
        equity_df = pd.DataFrame(self.equity_curve)
        if equity_df.empty or len(self.trades) < 2:
            return {
                "initial_cash": self.initial_cash,
                "final_cash": self.cash,
                "total_return_pct": (self.cash / self.initial_cash - 1) * 100,
                "num_trades": 0,
                "sharpe_ratio": 0,
                "max_drawdown_pct": 0,
                "win_rate_pct": 0,
                "trades": pd.DataFrame(self.trades),
                "equity_curve": equity_df,
            }

        # --- Calculate Metrics ---
        # Total Return
        total_return = (self.cash / self.initial_cash - 1) * 100

        # Sharpe Ratio (simple version, based on period returns)
        equity_df["returns"] = equity_df["equity"].pct_change().fillna(0)
        if equity_df["returns"].std() == 0:
            sharpe_ratio = 0.0
        else:
            # Assuming the data frequency allows for this annualization.
            # This might need adjustment for different timeframes (e.g., 252 for daily, 252*6.5 for hourly)
            annualization_factor = np.sqrt(252) if len(equity_df) > 1 else 1
            sharpe_ratio = (equity_df["returns"].mean() / equity_df["returns"].std()) * annualization_factor

        # Max Drawdown
        equity_df["peak"] = equity_df["equity"].cummax()
        equity_df["drawdown"] = (equity_df["equity"] - equity_df["peak"]) / equity_df["peak"]
        max_drawdown = equity_df["drawdown"].min()

        # Win Rate
        trades_df = pd.DataFrame(self.trades)
        num_completed_trades = 0
        win_rate = 0
        if not trades_df.empty:
            buys = trades_df[trades_df['side'] == 'buy'].copy()
            sells = trades_df[trades_df['side'] == 'sell'].copy()
            
            if not buys.empty and not sells.empty:
                buys['trade_num'] = buys.groupby('symbol').cumcount()
                sells['trade_num'] = sells.groupby('symbol').cumcount()
                
                completed_trades = pd.merge(buys, sells, on=['symbol', 'trade_num'], suffixes=('_buy', '_sell'))
                
                if not completed_trades.empty:
                    pnl = (completed_trades["price_sell"] - completed_trades["price_buy"]) * completed_trades["qty_buy"]
                    wins = (pnl > 0).sum()
                    num_completed_trades = len(completed_trades)
                    win_rate = (wins / num_completed_trades) * 100 if num_completed_trades > 0 else 0

        results = {
            "initial_cash": self.initial_cash,
            "final_cash": self.cash,
            "total_return_pct": total_return,
            "num_trades": num_completed_trades,
            "sharpe_ratio": sharpe_ratio,
            "max_drawdown_pct": max_drawdown * 100,
            "win_rate_pct": win_rate,
            "trades": trades_df,
            "equity_curve": equity_df,
        }
        log.info(f"Final Portfolio Value: ${self.cash:,.2f}")
        log.info(f"Total Return: {total_return:.2f}%")
        log.info(f"Sharpe Ratio: {sharpe_ratio:.2f}")
        log.info(f"Max Drawdown: {max_drawdown*100:.2f}%")
        log.info(f"Win Rate: {win_rate:.2f}%")
        log.info(f"Total Trades: {num_completed_trades}")
        return results

