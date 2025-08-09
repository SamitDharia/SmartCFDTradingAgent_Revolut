Paste:

```markdown
# SmartCFD – where we are / how it works / how to run

## Where we are
- Version: **v0.1.4**
- Broker: **none** (manual execution in Revolut)
- Auto notifications: **Yes** (via Scheduled Tasks) + manual runs anytime

## How it works
1) Load `.env` (BOT_TOKEN, CHAT_ID) → Telegram ready.
2) Rank watchlist by 30-day Sharpe → take top-N.
3) Download prices (intraday uses tested period/interval combos `("7d","1h")`, `("30d","60m")`, `("30d","30m")`, `("7d","15m")` to satisfy Yahoo limits).
4) Signals = EMA + MACD filtered by ADX (optional multi-timeframe voting).
5) Build PRE-TRADE: side, price, **SL/TP**, **Qty≈** (ATR-based sizing within portfolio risk cap).
6) Send to Telegram + log to file; write to `storage/decision_log.csv`.
7) Wait `--grace` seconds → run 1-year backtest → send summary.
8) **Cooldown** suppresses repeated (ticker+side) alerts for N minutes.

## How to run (copy-paste)
Crypto (24/7):

python -m SmartCFDTradingAgent.pipeline --watch BTC-USD ETH-USD --size 2 --interval 1h --intervals 15m,1h,1d --vote --adx 10 --grace 10 --risk 0.01 --equity 1000 --cooldown-min 30

scss
Copy
Edit
Equities (market hours):
python -m SmartCFDTradingAgent.pipeline --watch SPY QQQ DIA IWM --size 4 --interval 1d --use-params --grace 120 --risk 0.01 --equity 1000 --max-portfolio-risk 0.02 --max-trades 2

makefile
Copy
Edit
Useful:
python -m SmartCFDTradingAgent.pipeline --show-decisions 10 --to-telegram
python -m SmartCFDTradingAgent.pipeline --daily-summary --tz Europe/Dublin
python -m SmartCFDTradingAgent.optimizer --watch SPY QQQ DIA IWM --interval 1d --years 2
python -m SmartCFDTradingAgent.revolut_recon --csv "C:\path\to\Revolut_trades.csv" --window-min 180 --to-telegram

markdown
Copy
Edit

## Automatic vs manual
- **Automatic**: Scheduled Tasks run `scripts\market_loop.cmd` (weekdays) and `scripts\nightly.cmd` (daily 22:30).  
  Set tasks to “Run whether user is logged on or not” to keep them going.
- **Manual**: run any of the commands above from the project venv.

## Where progress is saved
- Decisions → `SmartCFDTradingAgent/storage/decision_log.csv`
- Tuned params → `SmartCFDTradingAgent/storage/params.json`
- Cooldown → `SmartCFDTradingAgent/storage/last_signals.json`
- Logs → `SmartCFDTradingAgent/logs/YYYYMMDD.log`
- Recon → `SmartCFDTradingAgent/storage/recon_YYYY-MM-DD.csv`

## Quick troubleshooting
- “Market closed – skipping cycle” → add `--force` or run during market hours.
- Repeated alerts → adjust `--cooldown-min` or `del storage\last_signals.json`.
- Recon “FileNotFoundError” → use your real CSV path in quotes.
