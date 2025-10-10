import os
import logging
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Tuple, Dict, Any
import json
import time
from datetime import datetime, timezone
from functools import partial

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
        app_cfg, alpaca_cfg, _, _ = load_config_from_file() # Load config to get watchlist
        data_feed_status = check_data_feed_health(app_cfg, alpaca_cfg)
        component_statuses["data_feed"] = data_feed_status
    except Exception:
        log.error("health.compute.data_feed_fail", exc_info=True)
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

def start_health_server(app_config: Any, alpaca_config: Any) -> Thread:
    """
    Starts the health check server in a background thread.
    """
    def run_server():
        try:
            server_address = ('', 8080)
            
            # Use functools.partial to create a handler with the configs already filled in
            handler = partial(HealthCheckHandler, app_config, alpaca_config)

            httpd = HTTPServer(server_address, handler)
            log.info("health.server.running on port 8080")
            httpd.serve_forever()
        except Exception:
            log.warning("runner.health.server.fail", exc_info=True)

    health_thread = Thread(target=run_server, daemon=True)
    health_thread.start()
    log.info("runner.health.server.start")
    return health_thread


class HealthCheckHandler(BaseHTTPRequestHandler):
    """
    A simple HTTP handler for health checks.
    """
    def __init__(self, app_config: Any, alpaca_config: Any, *args, **kwargs):
        self.app_config = app_config
        self.alpaca_config = alpaca_config
        # BaseHTTPRequestHandler is an old-style class, so we call its __init__ this way
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == '/healthz':
            is_healthy, reason, components = compute_health(
                db_path=self.app_config.db_path,
                max_age_seconds=self.app_config.heartbeat_max_age_seconds,
                startup_grace_period=self.app_config.startup_grace_period
            )
            
            status_code = 200 if is_healthy else 503
            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            response = {
                "status": "healthy" if is_healthy else "unhealthy",
                "reason": reason,
                "components": components
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
        
        elif self.path == '/health/db':
            conn = connect(self.app_config.db_path)
            stats = get_heartbeat_stats(conn)
            conn.close()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(stats, indent=4).encode('utf-8'))

        elif self.path == '/health/data':
            data_health = check_data_feed_health(self.app_config, self.alpaca_config)
            status_code = 200 if data_health.get("ok") else 503
            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data_health).encode('utf-8'))

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

    def log_message(self, format, *args):
        # Override to suppress the default logging of requests to stderr
        return
