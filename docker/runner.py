import os
import time
import logging
import requests
import signal

from smartcfd.config import load_config
from smartcfd.logging_setup import setup_logging
from smartcfd.db import connect as db_connect, init_schema, record_run, record_heartbeat
from smartcfd.alpaca import build_api_base, build_headers_from_env
from smartcfd.health_server import start_health_server

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
    # On Windows, SIGINT is the only signal that can be sent to a subprocess
    # CTRL_C_EVENT and CTRL_BREAK_EVENT are handled by SIGINT
    signal.signal(signal.SIGINT, shutdown_handler)

    # Start /healthz server (optional)
    try:
        if os.getenv("RUN_HEALTH_SERVER", "1") not in ("0", "false", "False", "FALSE"):
            port = int(os.getenv("HEALTH_PORT", "8080"))
            max_age = int(os.getenv("HEALTH_MAX_AGE_SECONDS", "120"))
            start_health_server(port=port, db_path=None, max_age_seconds=max_age)
            log.info("runner.health.server.start", extra={"extra": {"port": port, "max_age_seconds": max_age}})
    except Exception as e:
        log.warning("runner.health.server.fail", extra={"extra": {"error": repr(e)}})

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
    try:
        while running:
            ok, detail, status_code, latency_ms, err = check_connectivity(api_base, cfg.api_timeout_seconds)

            if ok:
                log.info("runner.health.ok", extra={"extra": {"detail": detail, "latency_ms": latency_ms}})
                backoff = 2
            else:
                log.warning("runner.health.fail", extra={"extra": {"detail": detail, "latency_ms": latency_ms}})
                backoff = min(backoff * 2, int(cfg.network_max_backoff_seconds))

            try:
                if conn is not None:
                    record_heartbeat(
                        conn=conn,
                        ok=ok,
                        latency_ms=latency_ms,
                        status_code=status_code,
                        error=err,
                        note="connectivity",
                    )
            except Exception as e:
                log.debug("heartbeat.db.write.fail", extra={"extra": {"error": repr(e)}})

            log.info("runner.heartbeat", extra={"extra": {"sleep_seconds": backoff}})
            time.sleep(backoff)
    finally:
        try:
            if conn is not None:
                log.info("runner.stop")
                if run_id:
                    record_run(conn, status="stop", note="signal", run_id=run_id)
                conn.close()
        except Exception as e:
            log.error("runner.stop.fail", extra={"extra": {"error": repr(e)}})

if __name__ == "__main__":
    main()