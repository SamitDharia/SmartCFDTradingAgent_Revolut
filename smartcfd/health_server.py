import os
import logging
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Tuple, Dict, Any
import json
import time
from datetime import datetime, timezone

from smartcfd.db import connect, get_recent_heartbeats, get_heartbeat_stats
from smartcfd.health_checks import check_data_feed_health
from smartcfd.config import load_config_from_file

log = logging.getLogger("health")

# Global cache for health status to avoid constant re-computation
_health_status_cache = {
    "is_healthy": True,
    "reason": "ok",
    "components": {
        "database": {"ok": True, "reason": "ok"},
        "data_feed": {"ok": True, "reason": "ok"}
    }
}
_start_time = time.time()


def compute_health(db_path: Optional[str] = None, max_age_seconds: int = 120, startup_grace_period: int = 60) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Checks the latest heartbeat from the database and data feed health.
    Returns (is_healthy, overall_reason, component_statuses).
    """
    global _health_status_cache

    # During the grace period, report as healthy to allow startup to complete
    if time.time() - _start_time < startup_grace_period:
        return True, "startup_grace_period", _health_status_cache['components']

    component_statuses = {}

    # 1. Database Health
    try:
        conn = connect(db_path)
        try:
            beats = get_recent_heartbeats(conn, limit=1)
            if not beats:
                component_statuses["database"] = {"ok": False, "reason": "no_heartbeats"}
            else:
                latest = beats[0]
                # Check if the latest heartbeat is recent enough
                heartbeat_time = datetime.fromisoformat(latest['ts'])
                if (datetime.now(timezone.utc) - heartbeat_time).total_seconds() > max_age_seconds:
                    component_statuses["database"] = {"ok": False, "reason": "heartbeat_stale"}
                elif not latest["ok"]:
                    component_statuses["database"] = {"ok": False, "reason": "last_heartbeat_not_ok"}
                else:
                    component_statuses["database"] = {"ok": True, "reason": "ok"}
        finally:
            conn.close()
    except Exception as e:
        log.error("health.compute.db_fail", extra={"extra": {"error": repr(e)}})
        component_statuses["database"] = {"ok": False, "reason": "db_error"}

    # 2. Data Feed Health
    try:
        app_cfg, _, _ = load_config_from_file() # Load config to get watchlist
        data_feed_status = check_data_feed_health(app_cfg)
        component_statuses["data_feed"] = data_feed_status
    except Exception as e:
        log.error("health.compute.data_feed_fail", extra={"extra": {"error": repr(e)}})
        component_statuses["data_feed"] = {"ok": False, "reason": "check_failed_exception"}

    # 3. Determine Overall Health
    is_healthy = all(status["ok"] for status in component_statuses.values())
    if is_healthy:
        overall_reason = "ok"
    else:
        # Aggregate reasons from failed components
        overall_reason = ";".join(
            f"{name}:{status['reason']}"
            for name, status in component_statuses.items() if not status["ok"]
        )
    
    # Update cache
    _health_status_cache = {
        "is_healthy": is_healthy,
        "reason": overall_reason,
        "components": component_statuses
    }
    
    return is_healthy, overall_reason, component_statuses


class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            # The compute_health function now updates a global cache.
            # The server thread will call this periodically.
            # Here, we just read from the cache.
            status = _health_status_cache
            is_healthy = status["is_healthy"]

            # Override health status during grace period
            if time.time() - _start_time < 60: # Use a fixed value here for simplicity
                is_healthy = True
            
            if is_healthy:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')
            else:
                self.send_response(503)
                self.send_header("Content-type", "application/json")
                response_body = {
                    "status": "unhealthy",
                    "reason": status["reason"],
                    "details": status["components"]
                }
                self.wfile.write(json.dumps(response_body).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

class HealthCheckServer(Thread):
    def __init__(self, port: int, db_path: Optional[str], max_age_seconds: int, check_interval: int = 15):
        super().__init__()
        self.port = port
        self.db_path = db_path
        self.max_age_seconds = max_age_seconds
        self.check_interval = check_interval
        self.httpd = None
        self.daemon = True

    def run(self):
        # Start the HTTP server in a separate thread
        server_thread = Thread(target=self._run_server, daemon=True)
        server_thread.start()

        # Periodically compute health status and update the cache
        while True:
            compute_health(self.db_path, self.max_age_seconds)
            time.sleep(self.check_interval)

    def _run_server(self):
        self.httpd = HTTPServer(("", self.port), HealthCheckHandler)
        log.info(f"health.server.running on port {self.port}")
        self.httpd.serve_forever()

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()


def start_health_server(port: int, db_path: Optional[str], max_age_seconds: int):
    server = HealthCheckServer(port, db_path, max_age_seconds)
    server.start()
    return server
