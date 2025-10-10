import logging
import pandas as pd
from smartcfd.data_loader import DataLoader, is_data_stale, has_data_gaps, parse_interval
from smartcfd.config import AppConfig, AlpacaConfig

log = logging.getLogger(__name__)

def check_data_feed_health(app_config: AppConfig, alpaca_config: AlpacaConfig) -> dict:
    """
    Performs a health check on the data feed for the primary symbol.

    Returns:
        A dictionary containing health status details.
    """
    primary_symbol = app_config.watch_list.split(',')[0]
    interval = app_config.trade_interval
    
    api_base = "https://paper-api.alpaca.markets" if app_config.alpaca_env == "paper" else "https://api.alpaca.markets"
    loader = DataLoader(
        api_key=alpaca_config.key_id,
        secret_key=alpaca_config.secret_key,
        api_base=api_base
    )
    
    log.info("health_checks.data_feed.start", extra={"extra": {"symbol": primary_symbol}})
    
    try:
        # Fetch a small amount of recent data for validation
        data = loader.get_market_data(symbols=[primary_symbol], interval=interval, limit=50)
        
        if not isinstance(data, dict) or primary_symbol not in data or data[primary_symbol].empty:
            log.error("health_checks.data_feed.no_data")
            return {"ok": False, "reason": "no_data_received"}

        symbol_df = data[primary_symbol]

        # Perform integrity checks
        is_stale_flag = is_data_stale(symbol_df, max_staleness_minutes=30)
        has_gaps_flag = has_data_gaps(symbol_df, parse_interval(interval))

        if is_stale_flag or has_gaps_flag:
            reason = []
            if is_stale_flag: reason.append("data_stale")
            if has_gaps_flag: reason.append("data_gaps")
            log.warning("health_checks.data_feed.validation_failed", extra={"extra": {"reason": reason}})
            return {"ok": False, "reason": "_".join(reason)}

        log.info("health_checks.data_feed.ok")
        return {"ok": True, "reason": "ok"}

    except Exception:
        log.error("health_checks.data_feed.fail", exc_info=True)
        return {"ok": False, "reason": "check_failed_exception"}
