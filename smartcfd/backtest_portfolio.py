"""
A simple portfolio manager for backtesting simulations.
"""
import logging

log = logging.getLogger(__name__)

class BacktestPortfolio:
    """
    Manages the state of a portfolio during a backtest, including cash,
    positions, and equity.
    """
    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.positions = {}  # {symbol: qty}
        self.equity_history = []

    def update_equity(self, current_prices: dict):
        """
        Calculates and records the current total equity of the portfolio.
        Equity = cash + value of all positions at current prices.
        """
        total_position_value = 0.0
        for symbol, qty in self.positions.items():
            if symbol in current_prices:
                total_position_value += qty * current_prices[symbol]
        
        current_equity = self.cash + total_position_value
        self.equity_history.append(current_equity)
        return current_equity

    def execute_order(self, symbol: str, qty: float, side: str, price: float):
        """
        Updates the portfolio based on a simulated order execution.
        """
        cost = qty * price
        if side == 'buy':
            if self.cash < cost:
                log.warning("Not enough cash to execute buy order. Order rejected.")
                return False
            self.cash -= cost
            self.positions[symbol] = self.positions.get(symbol, 0) + qty
        elif side == 'sell':
            current_qty = self.positions.get(symbol, 0)
            if qty > current_qty:
                log.warning(f"Cannot sell {qty} {symbol}, only hold {current_qty}. Order rejected.")
                return False
            self.cash += cost
            self.positions[symbol] -= qty
            if self.positions[symbol] == 0:
                del self.positions[symbol]
        else:
            log.error(f"Unknown order side: {side}")
            return False
        
        return True

    def get_total_equity(self, current_prices: dict = None) -> float:
        """
        Calculates the current total equity of the portfolio.
        Equity = cash + value of all positions.
        If current_prices is provided, it calculates based on them.
        Otherwise, it returns the last known equity from its history.
        """
        if current_prices:
            total_position_value = 0.0
            for symbol, qty in self.positions.items():
                if symbol in current_prices:
                    total_position_value += qty * current_prices[symbol]
            return self.cash + total_position_value
        
        if not self.equity_history:
            return self.initial_capital
            
        return self.equity_history[-1]
