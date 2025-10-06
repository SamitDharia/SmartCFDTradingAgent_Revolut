import os
import signal
import subprocess
import time
import pytest
from smartcfd.db import connect, get_latest_runs

@pytest.fixture
def db_path(tmp_path):
    """Fixture to provide a temporary database path and ensure cleanup."""
    path = tmp_path / "test_shutdown.db"
    yield str(path)
    if path.exists():
        os.remove(path)

def test_runner_graceful_shutdown(db_path):
    """
    Verify that the runner handles SIGTERM gracefully, updating the run record to 'stop'.
    """
    # 1. Setup environment for the subprocess
    env = os.environ.copy()
    env["PYTHONPATH"] = "."
    env["DB_PATH"] = db_path
    env["RUN_HEALTH_SERVER"] = "0"  # Disable health server to avoid port conflicts
    env["DANGEROUSLY_DISABLE_SSL_VERIFICATION"] = "1"

    # 2. Start the runner as a subprocess
    # Use lists for Popen arguments for cross-platform compatibility
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    process = subprocess.Popen(
        ["python", "-m", "docker.runner"],
        env=env,
        creationflags=creationflags,
    )

    try:
        # 3. Wait a moment for the runner to start and create the 'start' record
        time.sleep(5)  # Increased sleep to allow for slower CIs

        # 4. Send SIGTERM/CTRL_BREAK to the process
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.send_signal(signal.SIGTERM)

        # 5. Wait for the process to terminate
        process.wait(timeout=10)

        # 6. Verify the database record
        conn = connect(db_path)
        try:
            latest_runs = get_latest_runs(conn, limit=1)
            assert len(latest_runs) == 1
            latest_run = latest_runs[0]
            assert latest_run["status"] == "stop"
            assert latest_run["note"] == "signal"
            assert latest_run["stopped_at"] is not None
        finally:
            conn.close()

    finally:
        # Ensure the process is terminated, even if the test fails
        if process.poll() is None:
            if hasattr(os, "setsid"):
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            else:
                process.kill()
            process.wait()
