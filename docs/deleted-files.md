# Deletion Ledger

This file tracks removed/merged legacy files as part of the cleanup.

For each deletion, add an entry:
- Path:
- Reason:
- Replacement (if any):
- PR/Commit:
- Notes:

Examples:
- Path: src/telegram/bot.py
  Reason: Removed Telegram module per new architecture
  Replacement: N/A
  PR/Commit: <filled on delete>
  Notes: No remaining references (verified)

- Path: scripts/crypto_backfill.py
  Reason: Not required for performance metrics under Alpaca-only flow
  Replacement: N/A
  PR/Commit: <filled on delete>
  Notes: Removed and import graph passes