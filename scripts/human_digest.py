#!/usr/bin/env python3
"""Generate a plain-language trading digest and optionally send to Telegram."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from SmartCFDTradingAgent.reporting import Digest
from SmartCFDTradingAgent.utils.telegram import send


DEFAULT_OUT = Path("reports") / "daily_digest.txt"
DEFAULT_JSON = Path("reports") / "daily_digest.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Produce a client-friendly trade digest")
    parser.add_argument("--decisions", type=int, default=5, help="How many recent decisions to include")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Where to save the text report")
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON, help="Where to save structured JSON")
    parser.add_argument("--to-telegram", action="store_true", help="Send the digest via Telegram as well")
    args = parser.parse_args(argv)

    load_dotenv()
    digest = Digest()
    text = digest.generate_text(decisions=args.decisions)

    digest.save_digest(text, args.out)
    digest.dump_json(digest.latest_decisions(args.decisions), args.json)

    print(f"Digest saved to {args.out}")

    if args.to_telegram:
        if send(text):
            print("Digest sent to Telegram")
        else:
            print("Warning: Telegram send failed. Check your .env settings.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
