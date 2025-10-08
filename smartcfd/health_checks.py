import logging
import pandas as pd
from smartcfd.data_loader import DataLoader, is_data_stale, has_data_gaps, has_anomalous_data
from smartcfd.config import AppConfig

log = logging.getLogger(__name__)

def check_data_feed_health(config: AppConfig) -> dict:
    """
    Performs a health check on the data feed for the primary symbol.

    Returns:
        A dictionary containing health status details.
    """
    primary_symbol = config.watch_list.split(',')[0]
    interval = config.trade_interval
    loader = DataLoader()
    
    log.info("health_checks.data_feed.start", extra={"extra": {"symbol": primary_symbol}})
    
    try:
        # Fetch a small amount of recent data for validation
        data = loader.get_market_data(symbols=[primary_symbol], interval=interval, limit=50)
        
        if not isinstance(data, dict) or primary_symbol not in data or data[primary_symbol].empty:
            log.error("health_checks.data_feed.no_data")
            return {"ok": False, "reason": "no_data_received"}

        symbol_df = data[primary_symbol]

        # Perform integrity checks
        # Use a slightly more tolerant staleness for a health check
        is_stale_flag = is_data_stale(symbol_df, max_staleness_minutes=30)
        has_gaps_flag = has_data_gaps(symbol_df, loader.client.parse_interval(interval))
        is_anomalous_flag = has_anomalous_data(symbol_df)

        if is_stale_flag or has_gaps_flag or is_anomalous_flag:
            reason = []
            if is_stale_flag: reason.append("data_stale")
            if has_gaps_flag: reason.append("data_gaps")
            if is_anomalous_flag: reason.append("data_anomalous")
            log.warning("health_checks.data_feed.validation_failed", extra={"extra": {"reason": reason}})
            return {"ok": False, "reason": "_".join(reason)}

        log.info("health_checks.data_feed.ok")
        return {"ok": True, "reason": "ok"}

    except Exception as e:
        log.error("health_checks.data_feed.fail", exc_info=True)
        return {"ok": False, "reason": "check_failed_exception"}
