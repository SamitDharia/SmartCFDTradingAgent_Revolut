import csv
import sqlite3
from pathlib import Path
from typing import Any, Dict
from datetime import datetime, timezone

STORE = Path(__file__).resolve().parent.parent / "storage"
STORE.mkdir(exist_ok=True)

FIELDS = [
    "time",
    "ticker",
    "side",
    "entry",
    "sl",
    "tp",
    "exit",
    "exit_reason",
    "atr",
    "r_multiple",
    "fees",
    "broker",
    "order_id",
]

CSV_PATH = STORE / "trade_log.csv"
DB_PATH = STORE / "trade_log.sqlite"


def _ensure_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            time TEXT,
            ticker TEXT,
            side TEXT,
            entry REAL,
            sl REAL,
            tp REAL,
            exit REAL,
            exit_reason TEXT,
            atr REAL,
            r_multiple REAL,
            fees REAL,
            broker TEXT,
            order_id TEXT
        )
        """
    )
    return conn


def log_trade(row: Dict[str, Any]) -> None:
    """Append a trade row to CSV and SQLite log files.

    Missing fields are set to ``None``. If ``time`` is absent, the current
    timestamp is used.
    """
    data = {k: row.get(k) for k in FIELDS}
    if not data.get("time"):
        data["time"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # CSV
    new_file = not CSV_PATH.exists()
    with CSV_PATH.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow(data)

    # SQLite
    conn = _ensure_db()
    with conn:
        conn.execute(
            "INSERT INTO trades (" + ",".join(FIELDS) + ") VALUES (" + ",".join(["?"] * len(FIELDS)) + ")",
            [data[k] for k in FIELDS],
        )
    conn.close()


def aggregate_trade_stats() -> Dict[str, int]:
    """Return counts of wins, losses and open trades.

    A trade is considered "open" when its ``exit`` field is ``NULL``.  Closed
    trades are split into wins and losses based on whether the exit price was
    favourable relative to the entry price for the given trade ``side``.
    """

    conn = _ensure_db()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                SUM(
                    CASE
                        WHEN exit IS NOT NULL AND entry IS NOT NULL
                             AND ((side = 'buy' AND exit > entry)
                                  OR (side = 'sell' AND exit < entry))
                        THEN 1 ELSE 0
                    END
                ) AS wins,
                SUM(
                    CASE
                        WHEN exit IS NOT NULL AND entry IS NOT NULL
                             AND ((side = 'buy' AND exit <= entry)
                                  OR (side = 'sell' AND exit >= entry))
                        THEN 1 ELSE 0
                    END
                ) AS losses,
                SUM(CASE WHEN exit IS NULL THEN 1 ELSE 0 END) AS open
            FROM trades
            """,
        )
        wins, losses, open_trades = cur.fetchone()
        return {
            "wins": int(wins or 0),
            "losses": int(losses or 0),
            "open": int(open_trades or 0),
        }
    finally:
        conn.close()
