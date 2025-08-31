# SmartCFDTradingAgent – Revolut

Rank assets, generate signals, and send manual execution alerts via Telegram (with SL/TP).

## Developer setup

See [AGENTS.md](AGENTS.md) for environment setup, linting, formatting, testing, and smoke/backtest instructions.

This project targets Python 3.10–3.11 where pre-built pandas wheels are available.
Windows users running Python 3.12+ must install MSVC Build Tools to compile pandas or
downgrade Python to 3.11/3.10.

## .env configuration
Create a bot with @BotFather and copy `.env.example` to `.env` (do not commit):

```
cp .env.example .env
```

Fill in the variables:

```
TELEGRAM_BOT_TOKEN=123456:ABC-XYZ
TELEGRAM_CHAT_ID=123456789
```

Additional optional settings are available in `.env.example` such as
`SKIP_SSL_VERIFY`, `RISK_PCT`, `MAX_POSITIONS`, `MAX_DAILY_LOSS_PCT`,
`MARKET_GATE`, and `ALLOW_FRACTIONAL`.

### Scheduler environments
When running from Windows Task Scheduler or cron, ensure the job starts in the
project root so the `.env` file is discovered.  These schedulers launch with a
minimal environment, so credentials may need to be exported explicitly.

Example cron entry invoking a one-off Telegram test:

```
* * * * * cd /path/to/SmartCFDTradingAgent_Revolut && \
TELEGRAM_BOT_TOKEN=123456:ABC-XYZ TELEGRAM_CHAT_ID=123456789 \
python -c "from SmartCFDTradingAgent.utils.telegram import send; send('test')"
```

Windows Task Scheduler users should set **Start in** to the project root and
include environment variables in the command. See [Scheduling on Windows](#scheduling-on-windows)
for a step-by-step guide and sample command.

## Asset categories
Tickers are grouped into asset classes in `SmartCFDTradingAgent/assets.yml` (e.g. `crypto`, `equity`, `forex`, `commodity`).
These categories drive per-class alert caps and risk budgets via the `class_caps` and
`class_risk_budget` options in configuration files or CLI arguments.

## Run examples
Weekday equities (NYSE hours):
```
python -m SmartCFDTradingAgent.pipeline --watch SPY QQQ DIA IWM --size 3 --interval 1d --adx 15 --grace 120 --risk 0.01 --equity 1000
```
Weekend crypto (24/7; no --force needed):
```
python -m SmartCFDTradingAgent.pipeline --watch BTC-USD ETH-USD --size 2 --interval 1h --adx 10 --grace 10 --risk 0.01 --equity 1000
```
Config-based profile run:
```
python -m SmartCFDTradingAgent.pipeline --config configs/crypto.yml --profile crypto_1h
```

Multi-asset example with per-class caps and risk budgets:
```
python -m SmartCFDTradingAgent.pipeline --config configs/multi_asset.yml --profile multi_example
```

Weighted multi-interval voting:
```
python -m SmartCFDTradingAgent.pipeline --watch BTC-USD ETH-USD --interval 1h --intervals 15m,1h --interval-weights 15m=1,1h=2 --vote
```

## New flags & features (v0.1.1)
- `--interval` (e.g., `1h`, `30m`, `15m`) and `--adx` are configurable.
- Multi-interval voting via `--intervals`/`--vote` with optional weights
  (`--interval-weights 15m=1,1h=2`).
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

## Parameter tuning
Optimize parameters and save them to `SmartCFDTradingAgent/storage/params.json`:
```
python -m SmartCFDTradingAgent.optimizer --watch BTC-USD ETH-USD --interval 1h --years 2
```
Walk-forward validation (writes to the same params file):
```
python -m SmartCFDTradingAgent.walk_forward --watch BTC-USD ETH-USD --interval 1h --years 3 --train-months 6 --test-months 1
```

## Logs and decisions
Logs are written under `logs/`. Inspect the latest log, for example:
```
ls logs/
tail -n 20 logs/<recent-log>.log
```
Pre-trade decisions accumulate in `SmartCFDTradingAgent/storage/decision_log.csv`:
```
tail -n 20 SmartCFDTradingAgent/storage/decision_log.csv
```

## Automation

The `scripts` directory contains Unix-friendly `.sh` helpers mirroring the Windows `.cmd` files.

Both `market_loop.cmd` and `market_loop.sh` forward any extra CLI flags to the
underlying `run_bot` call and include `--dry-run` by default to avoid placing
real orders. Remove `--dry-run` if you intend to trade live and pass additional
options at invocation time, for example:

```
scripts/market_loop.cmd --force
scripts/market_loop.sh --force
```

### Cron (Unix)
Schedule runs with `crontab -e`. For example, to execute the market loop at 14:30 UTC every weekday:

```
30 14 * * 1-5 /path/to/SmartCFDTradingAgent_Revolut/scripts/market_loop.sh >> /path/to/market_loop.log 2>&1
```

This entry invokes `market_loop.sh` with the same CLI options as its Windows counterpart. Adjust the schedule and paths to suit your environment. See [docs/linux-scheduling.md](docs/linux-scheduling.md) for more examples.

### Scheduling on Windows
1. Open **Task Scheduler** and choose **Create Basic Task...**.
2. Select a trigger (daily, at startup, etc.) and proceed to the **Action** step.
3. Set **Program/script** to `cmd` and **Add arguments** to:

   ```
   /c "set TELEGRAM_BOT_TOKEN=123456:ABC-XYZ && set TELEGRAM_CHAT_ID=123456789 && python -m SmartCFDTradingAgent.pipeline --config configs/crypto.yml --profile crypto_1h"
   ```

4. In **Start in**, browse to the project root (where `.env` resides).
5. Finish the wizard and ensure the task runs under an account with the required permissions.

The `set` commands above define environment variables for the task before launching Python. Adjust the command and schedule for your environment. See [docs/windows-scheduling.md](docs/windows-scheduling.md) for more examples.
