#!/usr/bin/env python3
"""Generate a plain-language trading digest and optionally send to Telegram/email."""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from dotenv import load_dotenv

from SmartCFDTradingAgent.reporting import Digest
from SmartCFDTradingAgent.utils.telegram import send
from SmartCFDTradingAgent.emailer import send_email, default_recipients


DEFAULT_OUT = Path("reports") / "daily_digest.txt"
DEFAULT_JSON = Path("reports") / "daily_digest.json"


def _parse_extra_addresses(raw: str) -> list[str]:
    return [addr.strip() for addr in raw.split(",") if addr.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Produce a client-friendly trade digest")
    parser.add_argument("--decisions", type=int, default=5, help="How many recent decisions to include")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Where to save the text report")
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON, help="Where to save structured JSON")
    parser.add_argument("--to-telegram", action="store_true", help="Send the digest via Telegram as well")
    parser.add_argument("--email", action="store_true", help="Email the digest to subscribers")
    parser.add_argument("--email-to", default="", help="Comma separated extra email recipients")
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

    if args.email:
        recipients = default_recipients()
        extra = _parse_extra_addresses(args.email_to)
        recipients = list(dict.fromkeys(recipients + extra))  # deduplicate preserve order
        if recipients:
            subject = f"Daily Trading Digest - {dt.datetime.now():%Y-%m-%d}"
            try:
                send_email(subject, text, recipients)
                print(f"Digest emailed to: {', '.join(recipients)}")
            except RuntimeError as exc:
                print(f"Warning: {exc}", file=sys.stderr)
        else:
            print("Warning: No email recipients configured (set DIGEST_EMAILS or pass --email-to).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
