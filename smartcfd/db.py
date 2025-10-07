import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional

def get_db_path(default: str = "app.db") -> str:
    return os.getenv("DB_PATH", default)

def _ensure_parent(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)

def connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    p = db_path or get_db_path()
    _ensure_parent(p)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn

def init_schema(conn: sqlite3.Connection) -> None:
    # Runs table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            stopped_at TEXT,
            status TEXT NOT NULL,
            note TEXT
        )
        """
    )
    # Heartbeats table
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS heartbeats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            ok INTEGER NOT NULL,
            latency_ms REAL,
            status_code INTEGER,
            error TEXT,
            note TEXT
        )
        """
    )
    conn.commit()

def record_run(
    conn: sqlite3.Connection,
    status: str,
    note: Optional[str] = None,
    started_at: Optional[str] = None,
    run_id: Optional[int] = None,
) -> int:
    if run_id:
        # Update existing run
        ts = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            "UPDATE runs SET status = ?, note = ?, stopped_at = ? WHERE id = ?",
            (status, note, ts, run_id),
        )
        conn.commit()
        return run_id

    # Insert new run
    ts = started_at or datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO runs (started_at, status, note) VALUES (?, ?, ?)",
        (ts, status, note),
    )
    conn.commit()
    return int(cur.lastrowid)

def get_latest_runs(conn: sqlite3.Connection, limit: int = 5) -> List[Dict]:
    cur = conn.execute(
        "SELECT id, started_at, stopped_at, status, note FROM runs ORDER BY id DESC LIMIT ?",
        (int(limit),),
    )
    rows = cur.fetchall()
    return [dict(r) for r in rows]

def record_heartbeat(
    conn: sqlite3.Connection,
    ok: bool,
    latency_ms: Optional[float] = None,
    status_code: Optional[int] = None,
    error: Optional[str] = None,
    note: Optional[str] = None,
    ts: Optional[str] = None,
) -> int:
    tstamp = ts or datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO heartbeats (ts, ok, latency_ms, status_code, error, note) VALUES (?, ?, ?, ?, ?, ?)",
        (tstamp, 1 if ok else 0, latency_ms, status_code, error, note),
    )
    conn.commit()
    return int(cur.lastrowid)

def get_recent_heartbeats(conn: sqlite3.Connection, limit: int = 10) -> List[Dict]:
    cur = conn.execute(
        "SELECT id, ts, ok, latency_ms, status_code, error, note FROM heartbeats ORDER BY id DESC LIMIT ?",
        (int(limit),),
    )
    rows = cur.fetchall()
    return [dict(r) for r in rows]

def get_daily_pnl(conn: Optional[sqlite3.Connection] = None) -> float:
    """
    Calculates the profit and loss for the current day.
    
    TODO: This is a placeholder. This should be calculated from a trades table.
    For now, it returns 0.0, so the drawdown check will not be triggered
    unless this function is mocked in tests.
    """
    return 0.0

def get_heartbeat_stats(conn: sqlite3.Connection, hours: int = 24) -> Dict:
    """
    Calculates heartbeat statistics over a given period.
    """
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    cur = conn.execute(
        "SELECT ok, latency_ms FROM heartbeats WHERE ts >= ?",
        (since.isoformat(),),
    )
    rows = cur.fetchall()
    
    total = len(rows)
    if total == 0:
        return {"uptime_pct": 0, "avg_latency_ms": 0, "total_checks": 0}
        
    ok_count = sum(1 for r in rows if r["ok"])
    latencies = [r["latency_ms"] for r in rows if r["latency_ms"] is not None]
    
    return {
        "uptime_pct": (ok_count / total) * 100 if total > 0 else 0,
        "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
        "total_checks": total,
    }
