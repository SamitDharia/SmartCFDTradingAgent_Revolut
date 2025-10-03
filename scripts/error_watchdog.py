#!/usr/bin/env python3
"""Watchdog that disables trading tasks when repeated errors are detected."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "SmartCFDTradingAgent" / "logs"
STORE_DIR = ROOT / "SmartCFDTradingAgent" / "storage"
STATE_PATH = STORE_DIR / "watchdog_state.json"
TASKS = [
    "SmartCFDTradingAgent_Alpaca",
    "SmartCFDTradingAgent_Crypto",
]
KEYWORDS = [
    "Data download failed",
    "Broker submit failed",
    "Telegram send returned False",
]


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_state(data: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def count_recent_errors(lookback_minutes: int) -> int:
    if not LOG_DIR.exists():
        return 0
    cutoff = dt.datetime.now() - dt.timedelta(minutes=lookback_minutes)
    count = 0
    for log_file in LOG_DIR.glob("*.log"):
        try:
            with log_file.open(encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if not any(keyword in line for keyword in KEYWORDS):
                        continue
                    ts_part = line.split(" - ", 1)[0].strip()
                    try:
                        ts = dt.datetime.strptime(ts_part, "%Y-%m-%d %H:%M:%S,%f")
                    except Exception:
                        continue
                    if ts >= cutoff:
                        count += 1
        except Exception:
            continue
    return count


def disable_tasks() -> list[str]:
    disabled: list[str] = []
    for task in TASKS:
        try:
            proc = subprocess.run(
                ["schtasks", "/Change", "/TN", task, "/DISABLE"],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0:
                disabled.append(task)
            else:
                disabled.append(f"{task} (failed: {proc.stdout or proc.stderr})")
        except Exception as exc:
            disabled.append(f"{task} (error: {exc})")
    return disabled


def send_telegram(message: str) -> None:
    try:
        from SmartCFDTradingAgent.utils.telegram import send
    except Exception:
        return
    if not send(message):
        sys.stderr.write("Watchdog could not deliver Telegram alert.\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Disable scheduled trading tasks on repeated errors")
    parser.add_argument("--threshold", type=int, default=int(os.getenv("WATCHDOG_ERROR_THRESHOLD", "3")))
    parser.add_argument("--lookback", type=int, default=int(os.getenv("WATCHDOG_LOOKBACK_MIN", "60")), help="Minutes to scan")
    args = parser.parse_args(argv)

    load_dotenv()

    errors = count_recent_errors(args.lookback)
    state = load_state()
    already_disabled = state.get("disabled", False)

    if errors <= args.threshold:
        print(f"Watchdog: {errors} error(s) in last {args.lookback} min (threshold {args.threshold}).")
        return 0

    if already_disabled:
        print(
            "Watchdog threshold exceeded again, but tasks were already disabled earlier. "
            "Investigate logs and re-enable tasks manually when ready."
        )
        return 0

    disabled = disable_tasks()
    state.update({
        "disabled": True,
        "timestamp": dt.datetime.utcnow().isoformat(),
        "errors": errors,
    })
    save_state(state)

    message = (
        "⚠️ Watchdog triggered. Detected "
        f"{errors} errors in the last {args.lookback} minutes. "
        "Disabled scheduled trading tasks: " + ", ".join(disabled) + ".\n"
        "Inspect logs under SmartCFDTradingAgent/logs, fix the issue, then re-enable via Task Scheduler."
    )
    send_telegram(message)
    print(message)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
