import os
import time
import logging
import requests
import signal

from smartcfd.config import load_config_from_file
from smartcfd.db import connect as db_connect, init_schema, record_run, record_heartbeat
from smartcfd.alpaca import build_api_base, build_headers_from_env
from smartcfd.health_server import start_health_server
from smartcfd.trader import Trader
from smartcfd.strategy import get_strategy_by_name
from smartcfd.alpaca_client import AlpacaBroker
from smartcfd.risk import RiskManager
from smartcfd.data_loader import DataLoader
from smartcfd.portfolio import PortfolioManager

# Global connection and run_id to be accessible by the signal handler
conn = None
run_id = None

def shutdown_handler(signum, frame):
    """Gracefully shut down the runner on SIGTERM or SIGINT."""
    log = logging.getLogger("runner")
    log.warning("runner.shutdown", extra={"extra": {"signal": signum}})
    # The main loop will be broken by setting running to False
    global running
    running = False

def main():
    global conn, run_id, running
    running = True
    log = logging.getLogger("runner")

    try:
        app_cfg, risk_cfg, alpaca_cfg = load_config_from_file()
    except (FileNotFoundError, ValueError) as e:
        log.critical(f"Failed to load configuration: {e}")
        return # Exit if config is missing or invalid

    api_base = f"https://paper-api.alpaca.markets" if app_cfg.alpaca_env == 'paper' else "https://api.alpaca.markets"

    if app_cfg.alpaca_env == "live":
        log.critical("="*80)
        log.critical("  LIVE TRADING MODE IS ACTIVE. THE BOT IS OPERATING WITH REAL MONEY. ")
        log.critical("="*80)
        log.warning("Please monitor the system closely. Stop the container immediately if you notice any unexpected behavior.")
        log.info("Pausing for 5 seconds to allow for review...")
        time.sleep(5)

    conn = None
    try:
        conn = db_connect()
        init_schema(conn)
        run_id = record_run(conn, status="start", note="runner")
    except Exception as e:
        log.warning("failed to init DB / record run", extra={"extra": {"error": repr(e)}})

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, shutdown_handler)
    # CTRL_C_EVENT and CTRL_BREAK_EVENT are handled by SIGINT/SIGBREAK
    signal.signal(signal.SIGINT, shutdown_handler)
    if os.name == "nt":
        signal.signal(signal.SIGBREAK, shutdown_handler)

    # Start /healthz server (optional)
    try:
        if os.getenv("RUN_HEALTH_SERVER", "1") not in ("0", "false", "False", "FALSE"):
            port = int(os.getenv("HEALTH_PORT", "8080"))
            max_age = int(os.getenv("HEALTH_MAX_AGE_SECONDS", "120"))
            start_health_server(port=port, db_path=None, max_age_seconds=max_age)
            log.info("runner.health.server.start", extra={"extra": {"port": port, "max_age_seconds": max_age}})
    except Exception as e:
        log.warning("runner.health.server.fail", extra={"extra": {"error": repr(e)}})

    # Initialize the Alpaca client, Risk Manager, and Strategy
    try:
        broker = AlpacaBroker(
            api_key=alpaca_cfg.api_key,
            secret_key=alpaca_cfg.secret_key,
            paper=(app_cfg.alpaca_env == 'paper')
        )
    except ValueError as e:
        log.critical(f"Failed to initialize broker: {e}")
        return

    # Pass the broker to the PortfolioManager
    portfolio_manager = PortfolioManager(broker)
    
    risk_manager = RiskManager(portfolio_manager, risk_cfg)
    strategy_name = os.getenv("STRATEGY", "inference")
    strategy = get_strategy_by_name(strategy_name)
    
    # Initialize the Trader
    trader = Trader(portfolio_manager, strategy, risk_manager, app_cfg)

    log.info(
        "runner.start",
        extra={
            "extra": {
                "tz": app_cfg.timezone,
                "env": app_cfg.alpaca_env,
                "api_base": api_base,
                "timeout": app_cfg.api_timeout_seconds,
                "strategy": strategy_name,
            }
        },
    )

    backoff_seconds = 1.0
    network_max_backoff = float(os.getenv("NETWORK_MAX_BACKOFF_SECONDS", "60"))

    while running:
        try:
            # The main trading logic is now wrapped in a try/except block
            # to handle potential API errors gracefully.
            if conn:
                # We can't easily measure latency here, so we'll record a placeholder
                record_heartbeat(conn, run_id, -1, "ok", 200)
            
            # Run the trading loop
            trader.run()
            backoff_seconds = 1.0  # Reset backoff on success

        except Exception as e:
            log.warning("runner.loop.fail", extra={"extra": {"error": repr(e)}})
            if conn:
                record_heartbeat(conn, run_id, -1, "error", 500)
            
            # Exponential backoff with jitter
            sleep_time = backoff_seconds + (os.urandom(1)[0] / 255.0)
            log.info(f"runner.backoff", extra={"extra": {"sleep_time": sleep_time}})
            time.sleep(sleep_time)
            backoff_seconds = min(backoff_seconds * 2, network_max_backoff)

        # Sleep for the configured interval
        log.info(f"runner.sleep", extra={"extra": {"interval": app_cfg.run_interval_seconds}})
        time.sleep(app_cfg.run_interval_seconds)

    log.info("runner.exit")
    if conn:
        record_run(conn, run_id, status="stop", note="runner")
        conn.close()

if __name__ == "__main__":
    main()