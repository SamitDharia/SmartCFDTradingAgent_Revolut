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
    # Trade Groups table for client-side OCO
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trade_groups (
            gid TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            status TEXT NOT NULL,
            entry_order_id TEXT,
            entry_filled_qty REAL,
            tp_order_id TEXT,
            sl_order_id TEXT,
            open_qty REAL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            note TEXT
        )
        """
    )
    # Order events table for telemetry
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS order_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            event_type TEXT NOT NULL,
            group_gid TEXT,
            symbol TEXT,
            order_client_id TEXT,
            broker_order_id TEXT,
            side TEXT,
            order_kind TEXT,
            qty REAL,
            price REAL,
            status TEXT,
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

def record_order_event(
    conn: sqlite3.Connection,
    event_type: str,
    group_gid: Optional[str] = None,
    symbol: Optional[str] = None,
    order_client_id: Optional[str] = None,
    broker_order_id: Optional[str] = None,
    side: Optional[str] = None,
    order_kind: Optional[str] = None,
    qty: Optional[float] = None,
    price: Optional[float] = None,
    status: Optional[str] = None,
    note: Optional[str] = None,
    ts: Optional[str] = None,
) -> int:
    tstamp = ts or datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        """
        INSERT INTO order_events (
            ts, event_type, group_gid, symbol, order_client_id, broker_order_id,
            side, order_kind, qty, price, status, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (tstamp, event_type, group_gid, symbol, order_client_id, broker_order_id,
         side, order_kind, qty, price, status, note),
    )
    conn.commit()
    # Also append to CSV for quick inspection
    try:
        import csv, os
        path = os.getenv("ORDER_EVENTS_CSV", "logs/order_events.csv")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        file_exists = os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["ts","event_type","group_gid","symbol","order_client_id","broker_order_id","side","order_kind","qty","price","status","note"])
            writer.writerow([tstamp,event_type,group_gid,symbol,order_client_id,broker_order_id,side,order_kind,qty,price,status,note])
    except Exception:
        pass
    return int(cur.lastrowid)

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
