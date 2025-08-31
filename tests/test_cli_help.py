import subprocess
import sys

def test_main_help():
    result = subprocess.run(
        [sys.executable, "-m", "SmartCFDTradingAgent.__main__", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "usage" in result.stdout.lower()
