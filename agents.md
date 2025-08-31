# AGENTS.md
## Setup
- Python 3.11+
- Windows: py -m venv venv && venv\Scripts\activate && pip install -r requirements.txt
- Unix/WSL: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

## Secrets
- Use env vars: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, ALPACA_KEY, ALPACA_SECRET
- Never commit .env

## Commands
- Lint: ruff check .
- Tests: pytest -q
- Smoke: python -m SmartCFDTradingAgent.__main__ --help
- Backtest: python -m SmartCFDTradingAgent.__main__ --tickers ETH BTC --start 2023-01-01 --end 2025-08-31 --backtest

## Code style
- Black + Ruff, type hints where touched, small focused PRs.
