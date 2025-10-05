import os
import time
import logging
import requests

from smartcfd.config import load_config
from smartcfd.logging_setup import setup_logging
from smartcfd.db import connect as db_connect, init_schema, record_run, record_heartbeat

def build_api_base(env: str) -> str:
    return "https://paper-api.alpaca.markets" if env.lower() == "paper" else "https://api.alpaca.markets"

def check_connectivity(api_base: str, timeout: float):
    start = time.perf_counter()
    try:
        r = requests.get(f"{api_base}/v2/clock", timeout=timeout)
        latency_ms = (time.perf_counter() - start) * 1000.0
        ok = r.status_code == 200
        return ok, str(r.status_code), r.status_code, latency_ms, None
    except Exception as e:
        latency_ms = (time.perf_counter() - start) * 1000.0
        return False, repr(e), None, latency_ms, repr(e)

def main():
    # Setup logging first
    setup_logging("INFO")
    log = logging.getLogger("runner")

    # Load configuration
    cfg = load_config()
    api_base = build_api_base(cfg.alpaca_env)

    # Open DB connection and prepare schema
    conn = None
    try:
        conn = db_connect()  # uses DB_PATH or default app.db
        init_schema(conn)
        record_run(conn, status="start", note="runner")
    except Exception as e:
        log.warning("failed to init DB / record run", extra={"extra": {"error": repr(e)}})

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
    try:
        while True:
            ok, detail, status_code, latency_ms, err = check_connectivity(api_base, cfg.api_timeout_seconds)

            if ok:
                log.info("runner.health.ok", extra={"extra": {"detail": detail, "latency_ms": latency_ms}})
                backoff = 2
            else:
                log.warning("runner.health.fail", extra={"extra": {"detail": detail, "latency_ms": latency_ms}})
                backoff = min(backoff * 2, int(cfg.network_max_backoff_seconds))

            # Record heartbeat to DB (best-effort)
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
                conn.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
