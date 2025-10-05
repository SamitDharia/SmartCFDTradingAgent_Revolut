from pathlib import Path
from smartcfd.db import connect, init_schema, record_run, get_latest_runs, get_db_path

def test_init_and_insert(tmp_path):
    dbfile = tmp_path / "test.db"
    conn = connect(str(dbfile))
    try:
        init_schema(conn)
        r1 = record_run(conn, status="ok", note="first")
        r2 = record_run(conn, status="ok", note="second")
        assert r2 > r1
        latest = get_latest_runs(conn, limit=10)
        assert len(latest) == 2
        assert latest[0]["note"] == "second"
        assert latest[1]["note"] == "first"
    finally:
        conn.close()

def test_env_db_path(tmp_path, monkeypatch):
    target = tmp_path / "env.db"
    monkeypatch.setenv("DB_PATH", str(target))
    conn = connect()
    try:
        init_schema(conn)
        record_run(conn, status="ok", note="env")
    finally:
        conn.close()
    assert Path(get_db_path()) == target
    assert target.exists()
