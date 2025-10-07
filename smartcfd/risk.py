import logging
from typing import List, Dict, Any, Optional
import pandas as pd
from pydantic import BaseModel

from smartcfd.alpaca_client import AlpacaClient, OrderRequest
from smartcfd.config import RiskConfig
from smartcfd.data_loader import DataLoader
from smartcfd.db import get_daily_pnl
from smartcfd.indicators import atr
from smartcfd.strategy import Strategy
from smartcfd.portfolio import Account, Position, PortfolioManager
from smartcfd.backtest_portfolio import BacktestPortfolio

log = logging.getLogger("risk")

class RiskManager:
    """
    Manages and enforces risk rules for trading.
    """
    def __init__(self, portfolio_manager: PortfolioManager, risk_config: RiskConfig):
        self.portfolio = portfolio_manager
        self.config = risk_config
        self.is_halted = False
        self.halt_reason = ""
        # This is a temporary solution until data loading is also centralized
        self.data_loader = DataLoader(api_base=portfolio_manager.client.api_base)


    def calculate_order_qty(self, symbol: str, side: str) -> float:
        """
        Calculates the quantity for an order based on risk rules, including
        risk per trade, max exposure per asset, and max total exposure.
        """
        log.info(
            "risk.calculate_order_qty.start",
            extra={"extra": {"symbol": symbol, "side": side}},
        )

        if self.is_halted:
            log.warning(
                "risk.calculate_order_qty.halted",
                extra={"extra": {"reason": self.halt_reason, "symbol": symbol}},
            )
            return 0.0

        account = self.portfolio.account
        if not account or not account.is_online:
            log.error(
                "risk.calculate_order_qty.no_account",
                extra={"extra": {"reason": "Cannot calculate quantity without online account info."}},
            )
            return 0.0

        try:
            equity = account.equity
            
            # Fetch the latest price for the symbol
            latest_trade = self.portfolio.client.get_latest_crypto_trade(symbol)
            if not latest_trade:
                log.error("risk.calculate_order_qty.no_price", extra={"extra": {"symbol": symbol}})
                return 0.0
            price = latest_trade['trade']['p']
            if price <= 0:
                log.error("risk.calculate_order_qty.invalid_price", extra={"extra": {"symbol": symbol, "price": price}})
                return 0.0

            # --- Rule 1: Risk per Trade ---
            risk_per_trade_amount = equity * (self.config.risk_per_trade_percent / 100.0)
            qty_by_risk = risk_per_trade_amount / price

            # --- Rule 2: Max Exposure per Asset ---
            max_asset_exposure_value = equity * (self.config.max_exposure_per_asset_percent / 100.0)
            current_asset_exposure = self.portfolio.get_exposure_for_symbol(symbol)
            available_asset_headroom = max_asset_exposure_value - current_asset_exposure
            qty_by_asset_limit = available_asset_headroom / price if available_asset_headroom > 0 else 0

            # --- Rule 3: Max Total Exposure ---
            max_total_exposure_value = equity * (self.config.max_total_exposure_percent / 100.0)
            current_total_exposure = self.portfolio.get_total_exposure()
            available_total_headroom = max_total_exposure_value - current_total_exposure
            qty_by_total_limit = available_total_headroom / price if available_total_headroom > 0 else 0

            # --- Final Quantity is the minimum of all constraints ---
            final_qty = min(qty_by_risk, qty_by_asset_limit, qty_by_total_limit)

            log.info(
                "risk.calculate_order_qty.constraints",
                extra={
                    "extra": {
                        "symbol": symbol, "price": price, "equity": equity,
                        "qty_by_risk": qty_by_risk,
                        "qty_by_asset_limit": qty_by_asset_limit,
                        "qty_by_total_limit": qty_by_total_limit,
                        "final_qty": final_qty,
                    }
                },
            )

            # Alpaca requires notional orders for crypto to be >= $1.
            if (final_qty * price) < 1.0:
                log.warning(
                    "risk.calculate_order_qty.too_small",
                    extra={"extra": {"symbol": symbol, "notional_value": final_qty * price}},
                )
                return 0.0

            return round(final_qty, 8)

        except Exception:
            log.error("risk.calculate_order_qty.fail", exc_info=True)
            return 0.0

    def _get_account_info(self) -> Optional[Account]:
        """DEPRECATED: Use portfolio_manager.account directly."""
        log.warning("risk._get_account_info.deprecated")
        return self.portfolio.account

    def _get_positions(self) -> List[Position]:
        """DEPRECATED: Use portfolio_manager.positions directly."""
        log.warning("risk._get_positions.deprecated")
        return list(self.portfolio.positions.values())

    def _check_volatility_for_symbol(self, symbol: str, interval: str) -> bool:
        """Checks if the volatility for a symbol exceeds the circuit breaker threshold."""
        multiplier = self.config.circuit_breaker_atr_multiplier
        if not multiplier or multiplier <= 0:
            return False # Circuit breaker is disabled

        # Fetch recent data to calculate ATR. We need enough for the ATR window + 1 for previous close.
        # TODO: This still uses a direct data loader. This could be refactored to use pre-fetched data.
        data = self.data_loader.get_market_data([symbol], interval, limit=50)
        if data is None or data.empty or len(data) < 2:
            log.warning("risk.volatility_check.no_data", extra={"extra": {"symbol": symbol, "reason": "Not enough data for volatility check."}})
            return False # Cannot perform check

        # Ensure data is sorted by time
        data = data.sort_index()

        # Calculate ATR for the series, excluding the most recent bar
        # Ensure we have enough data for the ATR calculation window
        atr_window = 14 # A common setting for ATR
        if len(data) < atr_window + 2:
            log.warning("risk.volatility_check.no_data", extra={"extra": {"symbol": symbol, "reason": "Not enough data for ATR calculation."}})
            return False

        historical_atr = atr(data['high'].iloc[:-1], data['low'].iloc[:-1], data['close'].iloc[:-1], window=atr_window).iloc[-1]

        # Calculate the True Range of the most recent bar
        last_bar = data.iloc[-1]
        prev_close = data['close'].iloc[-2]
        true_range = max(
            last_bar['high'] - last_bar['low'],
            abs(last_bar['high'] - prev_close),
            abs(last_bar['low'] - prev_close)
        )

        if historical_atr <= 0: # Avoid division by zero or nonsensical checks
            return False

        # Check if the current true range exceeds the historical average by the multiplier
        is_tripped = true_range > historical_atr * multiplier
        log.info(
            "risk.volatility_check.evaluate",
            extra={
                "extra": {
                    "symbol": symbol,
                    "is_tripped": is_tripped,
                    "true_range": true_range,
                    "historical_atr": historical_atr,
                    "multiplier": multiplier,
                }
            },
        )
        if is_tripped:
            self.is_halted = True
            self.halt_reason = f"Volatility circuit breaker tripped for {symbol}. True Range ({true_range:.2f}) > ATR ({historical_atr:.2f}) * {multiplier}"
            log.critical("risk.halt.volatility_exceeded", extra={"extra": {"symbol": symbol, "true_range": true_range, "atr": historical_atr, "multiplier": multiplier}})
            return True

        return False

    def check_for_halt(self, watch_list: List[str], interval: str) -> bool:
        """
        Checks all halt conditions. If any are met, sets the halt flag and returns True.
        If no conditions are met, it ensures the halt is lifted and returns False.
        """
        log.info("risk.check_for_halt.start")
        # --- Check for conditions that would CAUSE a halt ---

        # 1. Check for daily drawdown
        account = self.portfolio.account
        if account:
            try:
                equity = account.equity
                last_equity = account.last_equity
                drawdown = (equity / last_equity) - 1 if last_equity > 0 else 0
                
                is_exceeded = drawdown < self.config.max_daily_drawdown_percent
                log.info(
                    "risk.check_for_halt.drawdown_check",
                    extra={
                        "extra": {
                            "is_exceeded": is_exceeded,
                            "drawdown": drawdown,
                            "max_drawdown": self.config.max_daily_drawdown_percent,
                        }
                    },
                )
                if is_exceeded:
                    self.is_halted = True
                    self.halt_reason = f"Max daily drawdown exceeded: {drawdown:.2%} < {self.config.max_daily_drawdown_percent:.2%}"
                    log.critical("risk.halt.drawdown_exceeded", extra={"extra": {"drawdown": drawdown, "max_drawdown": self.config.max_daily_drawdown_percent}})
                    return True # Halt immediately
            except (ValueError, ZeroDivisionError):
                log.error("risk.halt_check.drawdown_error", exc_info=True)
                self.is_halted = True
                self.halt_reason = "Could not calculate drawdown due to invalid account data."
                return True
        else:
            log.error("risk.halt_check.no_account", extra={"extra": {"reason": "Cannot check drawdown without account info"}})
            # In a fail-safe mode, we might halt if we can't get account info
            self.is_halted = True
            self.halt_reason = "Could not retrieve account information to verify drawdown."
            return True

        # 2. Check for volatility circuit breaker for each symbol in the watch list
        for symbol in watch_list:
            if self._check_volatility_for_symbol(symbol, interval):
                self.is_halted = True # The reason is set inside the check
                return True # Halt immediately

        # --- If we've reached this point, no halt conditions were met ---
        if self.is_halted:
            log.info("risk.halt.reset", extra={"extra": {"reason": "All risk conditions are now normal."}})
            self.is_halted = False
            self.halt_reason = ""
        
        log.info("risk.check_for_halt.end", extra={"extra": {"is_halted": self.is_halted}})
        return self.is_halted
    
    def manage_open_positions(self, strategy: Strategy):
        """
        Manages open positions according to the defined strategy and risk rules.
        """
        log.info("risk.manage_open_positions.start")
        
        if self.is_halted:
            log.warning("risk.manage_open_positions.halted", extra={"extra": {"reason": self.halt_reason}})
            return # Do not manage positions if halted

        positions = list(self.portfolio.positions.values())
        if not positions:
            log.info("risk.manage_open_positions.no_positions")
            return # No positions to manage

        for position in positions:
            symbol = position.symbol
            qty = position.qty
            market_value = position.market_value
            unrealized_pl = position.unrealized_pl

            log.info("risk.manage_open_positions.evaluating", extra={"extra": {"symbol": symbol, "qty": qty, "market_value": market_value, "unrealized_pl": unrealized_pl}})
            
            # Example rule: Close positions with high unrealized loss
            if unrealized_pl < -100: # Arbitrary threshold for example
                log.info("risk.manage_open_positions.closing_loss", extra={"extra": {"symbol": symbol, "unrealized_pl": unrealized_pl}})
                # Here we would place a market order to close the position
                # self.client.close_position(symbol)
            
            # Example rule: Reduce position size if too large
            if qty > 10: # Arbitrary max qty for example
                new_qty = qty / 2
                log.info("risk.manage_open_positions.reducing_size", extra={"extra": {"symbol": symbol, "old_qty": qty, "new_qty": new_qty}})
                # Here we would place a reduce-only order
                # self.client.reduce_position_size(symbol, new_qty)
        
        log.info("risk.manage_open_positions.end")

    def is_drawdown_exceeded(self, account_equity: float) -> bool:
        """
        Checks if the current drawdown exceeds the maximum allowed drawdown.
        """
        daily_pnl = get_daily_pnl()
        drawdown_percent = (daily_pnl / account_equity) * 100 if account_equity > 0 else 0
        is_exceeded = drawdown_percent < self.config.max_daily_drawdown_percent
        log.info(
            "risk.is_drawdown_exceeded.check",
            extra={
                "extra": {
                    "is_exceeded": is_exceeded,
                    "daily_pnl": daily_pnl,
                    "account_equity": account_equity,
                    "drawdown_percent": drawdown_percent,
                }
            },
        )
        return is_exceeded

    def is_volatility_too_high(self, historical_data: pd.DataFrame, symbol: str) -> bool:
        """
        Checks if the current market volatility is too high to continue trading.
        A 'circuit breaker' based on the Average True Range (ATR).
        """
        atr_multiplier = self.config.circuit_breaker_atr_multiplier
        if atr_multiplier <= 0:
            return False  # Circuit breaker is disabled

        # We need at least `window + 1` periods to calculate ATR and have something to compare.
        window = 14
        if len(historical_data) < window + 1:
            log.warning(
                "risk.is_volatility_too_high.insufficient_data",
                extra={"extra": {"symbol": symbol, "data_length": len(historical_data)}},
            )
            return False

        # Calculate 14-period ATR
        atr_series = atr(historical_data['High'], historical_data['Low'], historical_data['Close'], window=window).dropna()

        if atr_series.empty:
            log.warning(
                "risk.is_volatility_too_high.atr_calculation_failed",
                extra={"extra": {"symbol": symbol}},
            )

        # Calculate the True Range of the last bar
        last_high = historical_data['High'].iloc[-1]
        last_low = historical_data['Low'].iloc[-1]
        prev_close = historical_data['Close'].iloc[-2]
        
        last_true_range = max(last_high - last_low, abs(last_high - prev_close), abs(last_low - prev_close))

        # Average of all available ATR values, excluding the influence of the last bar
        average_atr = atr_series.iloc[:-1].mean()

        if pd.isna(last_true_range) or pd.isna(average_atr) or average_atr == 0:
            return False # Cannot compute, play it safe

        threshold = average_atr * atr_multiplier

        if last_true_range > threshold:
            print(f"CIRCUIT BREAKER TRIPPED for {symbol}: Last TR ({last_true_range:.4f}) > Threshold ({threshold:.4f}) [Avg ATR: {average_atr:.4f}]")
            return True
        
        return False

        return False

class BacktestRiskManager:
    def __init__(self, risk_config: RiskConfig):
        self.config = risk_config

    def calculate_order_qty(self, symbol: str, price: float, portfolio: BacktestPortfolio) -> float:
        # Risk a percentage of total equity, not just available cash
        total_equity = portfolio.get_total_equity({symbol: price})
        risk_amount = total_equity * (self.config.risk_per_trade_percent / 100.0)
        
        # Calculate potential quantity based on risk amount
        qty = risk_amount / price

        # Enforce a minimum order size to avoid dust trades
        min_notional_value = 1.0  # $1 minimum, similar to Alpaca
        if (qty * price) < min_notional_value:
            # This is a common case (no signal or not enough to trade), so we don't log it
            # to avoid noise. A zero quantity is the intended result.
            return 0.0
        
        # Ensure we don't try to buy more than we have cash for
        if (qty * price) > portfolio.cash:
            log.debug(
                "risk.backtest.calculate_order_qty.cash_limited",
                extra={"extra": {"symbol": symbol, "requested_qty": qty, "cash_available": portfolio.cash, "price": price}}
            )
            qty = portfolio.cash / price
            # After adjusting for cash, re-check if it's still above the minimum notional value
            if (qty * price) < min_notional_value:
                log.debug(
                    "risk.backtest.calculate_order_qty.below_min_after_cash_limit",
                    extra={"extra": {"symbol": symbol, "adjusted_qty": qty, "notional_value": qty * price}}
                )
                return 0.0

        log.debug(
            "risk.backtest.calculate_order_qty.success",
            extra={
                "extra": {
                    "symbol": symbol,
                    "price": price,
                    "total_equity": total_equity,
                    "risk_per_trade_percent": self.config.risk_per_trade_percent,
                    "calculated_qty": qty,
                }
            },
        )
        return qty
