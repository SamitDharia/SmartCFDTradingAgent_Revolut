import os
import time
import logging
import requests
import signal

from smartcfd.config import load_config, load_risk_config
from smartcfd.logging_setup import setup_logging
from smartcfd.db import connect as db_connect, init_schema, record_run, record_heartbeat
from smartcfd.alpaca import build_api_base, build_headers_from_env
from smartcfd.health_server import start_health_server
from smartcfd.trader import Trader
from smartcfd.strategy import get_strategy_by_name
from smartcfd.broker import AlpacaBroker
from smartcfd.alpaca_client import get_alpaca_client
from smartcfd.risk import RiskManager

def check_connectivity(api_base: str, timeout: float):
    headers = build_headers_from_env()
    start = time.perf_counter()
    
    verify_ssl = os.getenv("DANGEROUSLY_DISABLE_SSL_VERIFICATION", "0") not in ("1", "true", "True")

    try:
        r = requests.get(f"{api_base}/v2/clock", timeout=timeout, headers=headers if headers else None, verify=verify_ssl)
        latency_ms = (time.perf_counter() - start) * 1000.0
        ok = r.status_code == 200
        return ok, str(r.status_code), r.status_code, latency_ms, None
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return False, repr(e), None, latency_ms, repr(e)

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
    setup_logging("INFO")
    log = logging.getLogger("runner")

    cfg = load_config()
    risk_cfg = load_risk_config()
    api_base = build_api_base(cfg.alpaca_env)

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
    alpaca_client = get_alpaca_client(api_base)
    broker = AlpacaBroker(alpaca_client)
    risk_manager = RiskManager(alpaca_client, risk_cfg)
    strategy_name = os.getenv("STRATEGY", "inference")
    strategy = get_strategy_by_name(strategy_name)
    
    # Initialize the Trader
    trader = Trader(strategy, broker, risk_manager)

    log.info(
        "runner.start",
        extra={
            "extra": {
                "tz": cfg.timezone,
                "env": cfg.alpaca_env,
                "api_base": api_base,
                "timeout": cfg.api_timeout_seconds,
                "strategy": strategy_name,
            }
        },
    )

    backoff_seconds = 1.0
    network_max_backoff = float(os.getenv("NETWORK_MAX_BACKOFF_SECONDS", "60"))

    while running:
        ok, status, code, latency, err = check_connectivity(api_base, cfg.api_timeout_seconds)
        if ok:
            backoff_seconds = 1.0  # Reset backoff on success
            if conn:
                record_heartbeat(conn, run_id, latency, "ok", code)
            
            # Run the trading loop
            trader.run()

        else:
            log.warning("runner.connectivity.fail", extra={"extra": {"status": status, "latency": latency, "error": err}})
            if conn:
                record_heartbeat(conn, run_id, latency, "error", code)
            
            # Exponential backoff with jitter
            sleep_time = backoff_seconds + (os.urandom(1)[0] / 255.0)
            log.info(f"runner.backoff", extra={"extra": {"sleep_time": sleep_time}})
            time.sleep(sleep_time)
            backoff_seconds = min(backoff_seconds * 2, network_max_backoff)

        # Sleep for the configured interval
        log.info(f"runner.sleep", extra={"extra": {"interval": cfg.run_interval_seconds}})
        time.sleep(cfg.run_interval_seconds)

    log.info("runner.exit")
    if conn:
        record_run(conn, run_id, status="stop", note="runner")
        conn.close()

if __name__ == "__main__":
    main()