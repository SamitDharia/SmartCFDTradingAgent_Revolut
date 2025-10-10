import os
import time
import logging
import requests
import signal

from smartcfd.config import load_config_from_file
from smartcfd.db import connect as db_connect, init_schema, record_run, record_heartbeat, record_order_event
from smartcfd.alpaca_helpers import build_api_base, build_headers_from_env
from smartcfd.health_server import start_health_server
from smartcfd.logging_setup import setup_logging
from smartcfd.regime_detector import RegimeDetector
from smartcfd.strategy import get_strategy_by_name, InferenceStrategy
from smartcfd.trader import Trader
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
    setup_logging() # Setup logging at the very beginning
    running = True
    log = logging.getLogger("runner")

    try:
        app_cfg, alpaca_cfg, risk_cfg, regime_cfg = load_config_from_file()
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
        # Start health server optionally
        if os.getenv("RUN_HEALTH_SERVER", "1") not in ("0", "false", "False", "FALSE"):
            start_health_server(app_cfg, alpaca_cfg)

        # Initialize Broker and DB connection
        broker = AlpacaBroker(key_id=alpaca_cfg.key_id, secret_key=alpaca_cfg.secret_key, paper=(app_cfg.alpaca_env == 'paper'))
        conn = db_connect()
        init_schema(conn)
        run_id = record_run(conn, status="start", note="runner")

        # Initialize managers
        portfolio_manager = PortfolioManager(broker)
        risk_manager = RiskManager(portfolio_manager, risk_cfg, broker)

        # Initialize the Trader
        log.info("runner.init.trader.start")
        trader = Trader(
            app_config=app_cfg,
            risk_config=risk_cfg,
            regime_config=regime_cfg,
            broker=broker,
            db_conn=conn,
            portfolio_manager=portfolio_manager,
            risk_manager=risk_manager
        )
        log.info("runner.init.trader.success")

        log.info("runner.start")

        # Main loop
        while running:
            try:
                # Record a heartbeat to show the runner is alive
                if conn:
                    record_heartbeat(conn, ok=True, note="runner")

                trader.run()

            except Exception:
                log.error("runner.loop.fail", exc_info=True)
            
            # Sleep in 1s intervals to allow signal handling
            sleep_duration = app_cfg.run_interval_seconds
            for _ in range(int(sleep_duration)):
                if not running:
                    break
                time.sleep(1)

        # --- Shutdown sequence ---
        log.info("runner.shutdown.start")
        if conn and run_id:
            record_run(conn, status="end", note="shutdown signal received", run_id=run_id)
        if conn:
            conn.close()
        log.info("runner.shutdown.complete")
    except Exception:
        log.warning("runner.main.fail", exc_info=True)


if __name__ == "__main__":
    main()
