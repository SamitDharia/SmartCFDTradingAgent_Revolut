from smartcfd.db import connect, init_schema, record_heartbeat, get_recent_heartbeats

def test_record_and_list_heartbeats(tmp_path):
    dbfile = tmp_path / "hb.db"
    conn = connect(str(dbfile))
    try:
        init_schema(conn)
        h1 = record_heartbeat(conn, ok=True, latency_ms=12.3, status_code=200, error=None, note="ok")
        h2 = record_heartbeat(conn, ok=False, latency_ms=45.6, status_code=401, error="unauthorized", note="fail")
        assert h2 > h1

        rows = get_recent_heartbeats(conn, limit=10)
        assert len(rows) == 2
        # newest first
        assert rows[0]["note"] == "fail"
        assert rows[0]["ok"] in (0, 1)
        # types / presence
        assert "latency_ms" in rows[0]
        assert "status_code" in rows[0]
        assert "error" in rows[0]
    finally:
        conn.close()
