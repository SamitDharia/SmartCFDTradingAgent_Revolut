import os
import logging
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional, Tuple, Dict, Any
from smartcfd.db import connect, get_recent_heartbeats

log = logging.getLogger("health")

def compute_health(db_path: Optional[str] = None, max_age_seconds: int = 120) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Checks the latest heartbeat from the database.
    Returns (is_healthy, reason, latest_heartbeat).
    """
    try:
        conn = connect(db_path)
        try:
            beats = get_recent_heartbeats(conn, limit=1)
            if not beats:
                return False, "no_heartbeats", None

            latest = beats[0]
            # TODO: Add freshness check based on max_age_seconds
            if not latest["ok"]:
                return False, "not_ok", latest

            return True, "ok", latest
        finally:
            conn.close()
    except Exception as e:
        log.error("health.compute.fail", extra={"extra": {"error": repr(e)}})
        return False, "db_error", None


class HealthCheckHandler(BaseHTTPRequestHandler):
    db_path: Optional[str] = None
    max_age_seconds: int = 120

    def do_GET(self):
        if self.path == "/healthz":
            is_healthy, reason, latest = compute_health(self.db_path, self.max_age_seconds)
            if is_healthy:
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status": "ok"}')
            else:
                self.send_response(503)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(f'{{"status": "unhealthy", "reason": "{reason}"}}'.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

def _run_server(port: int, db_path: Optional[str], max_age_seconds: int):
    """Target for the server thread."""
    handler = HealthCheckHandler
    handler.db_path = db_path
    handler.max_age_seconds = max_age_seconds
    
    server_address = ("", port)
    httpd = HTTPServer(server_address, handler)
    
    log.info("health.server.listen", extra={"extra": {"port": port}})
    httpd.serve_forever()

def start_health_server(port: int, db_path: Optional[str] = None, max_age_seconds: int = 120):
    """Starts the health check server in a background thread."""
    server_thread = Thread(
        target=_run_server,
        args=(port, db_path, max_age_seconds),
        daemon=True,
        name="HealthServer",
    )
    server_thread.start()
    log.info("health.server.started", extra={"extra": {"port": port}})
