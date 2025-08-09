# SmartCFDTradingAgent – Revolut (Alerts-Only, No Alpaca)

Rank assets, generate signals, and send manual execution alerts via Telegram (with SL/TP).

## Install (Windows)

```bat
cd C:\Projects\SmartCFDTradingAgent_Revolut
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Configure Telegram
Create a bot with @BotFather and set a local `.env` (do not commit):
```
BOT_TOKEN=123456:ABC-XYZ
CHAT_ID=123456789
```

## Run examples
Weekday equities (NYSE hours):
```
python -m SmartCFDTradingAgent.pipeline --watch SPY QQQ DIA IWM --size 3 --interval 1d --adx 15 --grace 120 --risk 0.01 --equity 1000
```
Weekend crypto (24/7; no --force needed):
```
python -m SmartCFDTradingAgent.pipeline --watch BTC-USD ETH-USD --size 2 --interval 1h --adx 10 --grace 10 --risk 0.01 --equity 1000
```

## New flags & features (v0.1.1)
- `--interval` (e.g., `1h`, `30m`, `15m`) and `--adx` are configurable.
- **Crypto 24/7**: all-crypto watchlists run outside NYSE hours.
- **Local timestamp**: `--tz Europe/Dublin` (default) or `--tz UTC`.
- **Decision log**: PRE-TRADE rows saved at `SmartCFDTradingAgent/storage/decision_log.csv`.
- Logger prints its log file path at startup.

## Reporting utilities
Show last 10 decisions in console:
```
python -m SmartCFDTradingAgent.pipeline --show-decisions 10
```
Show last 10 and send to Telegram:
```
python -m SmartCFDTradingAgent.pipeline --show-decisions 10 --to-telegram
```
Send today's summary to Telegram:
```
python -m SmartCFDTradingAgent.pipeline --daily-summary --tz Europe/Dublin
```
Cap the number of alerts in a run:
```
python -m SmartCFDTradingAgent.pipeline --watch SPY QQQ DIA IWM --size 4 --max-trades 2
```

## Automation

The `scripts` directory contains Unix-friendly `.sh` helpers mirroring the Windows `.cmd` files.

### Cron (Unix)
Schedule runs with `crontab -e`. For example, to execute the market loop at 14:30 UTC every weekday:

```
30 14 * * 1-5 /path/to/SmartCFDTradingAgent_Revolut/scripts/market_loop.sh >> /path/to/market_loop.log 2>&1
```

This entry invokes `market_loop.sh` with the same CLI options as its Windows counterpart. Adjust the schedule and paths to suit your environment.
