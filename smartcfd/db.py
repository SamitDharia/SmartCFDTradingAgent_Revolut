import os
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            status TEXT NOT NULL,
            note TEXT
        )
        """
    )
    conn.commit()

def record_run(conn: sqlite3.Connection, status: str, note: Optional[str] = None, started_at: Optional[str] = None) -> int:
    ts = started_at or datetime.now(timezone.utc).isoformat()
    cur = conn.execute(
        "INSERT INTO runs (started_at, status, note) VALUES (?, ?, ?)",
        (ts, status, note),
    )
    conn.commit()
    return int(cur.lastrowid)

def get_latest_runs(conn: sqlite3.Connection, limit: int = 5) -> List[Dict]:
    cur = conn.execute(
        "SELECT id, started_at, status, note FROM runs ORDER BY id DESC LIMIT ?",
        (int(limit),),
    )
    rows = cur.fetchall()
    return [dict(r) for r in rows]
