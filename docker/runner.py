import os
import time
import logging
import requests
from datetime import datetime, timezone

from smartcfd.config import load_config
from smartcfd.logging_setup import setup_logging
from smartcfd.db import connect as db_connect, init_schema, record_run

def build_api_base(env: str) -> str:
    return "https://paper-api.alpaca.markets" if env.lower() == "paper" else "https://api.alpaca.markets"

def check_connectivity(api_base: str, timeout: float) -> tuple[bool, str]:
    try:
        r = requests.get(f"{api_base}/v2/clock", timeout=timeout)
        ok = r.status_code == 200
        return ok, str(r.status_code)
    except Exception as e:
        return False, repr(e)

def main():
    # Setup logging first
    setup_logging("INFO")
    log = logging.getLogger("runner")

    # Load configuration
    cfg = load_config()
    api_base = build_api_base(cfg.alpaca_env)

    # Record a one-time run row (creates DB and schema if needed)
    try:
        conn = db_connect()  # uses DB_PATH or default app.db
        init_schema(conn)
        record_run(conn, status="start", note="runner")
        conn.close()
    except Exception as e:
        log.warning("failed to record run row", extra={"extra": {"error": repr(e)}})

    # Startup log
    log.info(
        "runner.start",
        extra={
            "extra": {
                "tz": cfg.timezone,
                "env": cfg.alpaca_env,
                "api_base": api_base,
                "timeout": cfg.api_timeout_seconds,
                "max_backoff": cfg.network_max_backoff_seconds,
            }
        },
    )

    backoff = 2
    while True:
        ok, detail = check_connectivity(api_base, cfg.api_timeout_seconds)
        if ok:
            log.info("runner.health.ok", extra={"extra": {"detail": detail}})
            backoff = 2
        else:
            log.warning("runner.health.fail", extra={"extra": {"detail": detail}})
            backoff = min(backoff * 2, int(cfg.network_max_backoff_seconds))

        log.info("runner.heartbeat", extra={"extra": {"sleep_seconds": backoff}})
        time.sleep(backoff)

if __name__ == "__main__":
    main()
