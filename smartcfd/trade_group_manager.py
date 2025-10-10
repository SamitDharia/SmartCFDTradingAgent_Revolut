import sqlite3
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from . import db
from .types import TradeGroup

class TradeGroupManager:
    """
    Manages the state of trade groups in the database for client-side OCO logic.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_group(self, symbol: str, side: str) -> TradeGroup:
        """
        Creates a new trade group record in the database.
        """
        now = datetime.now(timezone.utc).isoformat()
        gid = f"gid_{uuid.uuid4().hex}"
        
        group = TradeGroup(
            gid=gid,
            symbol=symbol,
            side=side,
            status="new",
            created_at=now,
            updated_at=now,
        )
        
        self.conn.execute(
            """
            INSERT INTO trade_groups (gid, symbol, side, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (group.gid, group.symbol, group.side, group.status, group.created_at, group.updated_at)
        )
        self.conn.commit()
        return group

    def update_group(self, gid: str, updates: Dict[str, Any]) -> Optional[TradeGroup]:
        """
        Updates an existing trade group.
        """
        updates['updated_at'] = datetime.now(timezone.utc).isoformat()
        
        fields = ", ".join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [gid]
        
        self.conn.execute(f"UPDATE trade_groups SET {fields} WHERE gid = ?", values)
        self.conn.commit()
        return self.get_group_by_gid(gid)

    def update_trade_group_entry(self, gid: str, entry_order_id: str):
        """Updates the entry order ID for a trade group."""
        self.update_group(gid, {"entry_order_id": entry_order_id})

    def update_trade_group_exits(self, gid: str, tp_order_id: str, sl_order_id: str):
        """Updates the exit order IDs for a trade group."""
        self.update_group(gid, {"tp_order_id": tp_order_id, "sl_order_id": sl_order_id})

    def update_trade_group_status(self, gid: str, status: str, note: Optional[str] = None):
        """Updates the status and optionally a note for a trade group."""
        updates = {"status": status}
        if note is not None:
            updates["note"] = note
        self.update_group(gid, updates)

    def get_group_by_gid(self, gid: str) -> Optional[TradeGroup]:
        """
        Retrieves a single trade group by its GID.
        """
        cur = self.conn.execute("SELECT * FROM trade_groups WHERE gid = ?", (gid,))
        row = cur.fetchone()
        if not row:
            return None
        keys = row.keys()
        return TradeGroup(
            gid=row['gid'],
            symbol=row['symbol'],
            side=row['side'],
            status=row['status'],
            entry_order_id=row['entry_order_id'] if 'entry_order_id' in keys else None,
            entry_filled_qty=row['entry_filled_qty'] if 'entry_filled_qty' in keys else None,
            tp_order_id=row['tp_order_id'] if 'tp_order_id' in keys else None,
            sl_order_id=row['sl_order_id'] if 'sl_order_id' in keys else None,
            open_qty=row['open_qty'] if 'open_qty' in keys else None,
            created_at=row['created_at'],
            updated_at=row['updated_at'],
            note=row['note'] if 'note' in keys else None,
        )

    def get_groups_by_status(self, status: str) -> List[TradeGroup]:
        """
        Retrieves all trade groups with a given status.
        """
        cur = self.conn.execute("SELECT * FROM trade_groups WHERE status = ?", (status,))
        rows = cur.fetchall()
        groups = []
        for row in rows:
            keys = row.keys()
            groups.append(TradeGroup(
                gid=row['gid'],
                symbol=row['symbol'],
                side=row['side'],
                status=row['status'],
                entry_order_id=row['entry_order_id'] if 'entry_order_id' in keys else None,
                entry_filled_qty=row['entry_filled_qty'] if 'entry_filled_qty' in keys else None,
                tp_order_id=row['tp_order_id'] if 'tp_order_id' in keys else None,
                sl_order_id=row['sl_order_id'] if 'sl_order_id' in keys else None,
                open_qty=row['open_qty'] if 'open_qty' in keys else None,
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                note=row['note'] if 'note' in keys else None,
            ))
        return groups

    def get_all_trade_groups(self) -> List[TradeGroup]:
        """
        Retrieves all trade groups from the database.
        """
        cur = self.conn.execute("SELECT * FROM trade_groups")
        rows = cur.fetchall()
        groups = []
        for row in rows:
            keys = row.keys()
            groups.append(TradeGroup(
                gid=row['gid'],
                symbol=row['symbol'],
                side=row['side'],
                status=row['status'],
                entry_order_id=row['entry_order_id'] if 'entry_order_id' in keys else None,
                entry_filled_qty=row['entry_filled_qty'] if 'entry_filled_qty' in keys else None,
                tp_order_id=row['tp_order_id'] if 'tp_order_id' in keys else None,
                sl_order_id=row['sl_order_id'] if 'sl_order_id' in keys else None,
                open_qty=row['open_qty'] if 'open_qty' in keys else None,
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                note=row['note'] if 'note' in keys else None,
            ))
        return groups
