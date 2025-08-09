# SmartCFDTradingAgent – Revolut Edition

> **Session Summary (append at the top every time):**
> - [YYYY-MM-DD HH:MM Europe/Dublin] Ran pipeline with: `--watch=... --interval=... --adx=... --grace=...`
> - Decisions logged → `SmartCFDTradingAgent/storage/decision_log.csv`
> - Log file → `SmartCFDTradingAgent/logs/YYYYMMDD.log`

---

## Current Version: v0.1.4

**What’s in this release**
- Telegram PRE-TRADE alerts (Buy/Sell, price, **SL/TP**, **Qty≈**)
- Strategy: EMA + MACD with **ADX** filter; optional **multi-timeframe voting** (e.g., 15m/1h/1d)
- **Intraday data fix**: uses tested period/interval combos `("7d","1h")`, `("30d","60m")`, `("30d","30m")`, `("7d","15m")`
- **ATR-based position size** hint + **max portfolio risk** cap
- **Cooldown** to suppress duplicate (ticker+side) alerts for N minutes
- **Backtest** snapshot after `--grace` delay
- **Decision log** CSV, **daily summary**, **optimizer** (saves tuned ADX/SL/TP to `params.json`)
- **Revolut reconciliation**: match your export CSV to decisions

**What we removed**
- Alpaca. (No broker code remains.)

---

## How to run (quick)
**Crypto (24/7):**
```bash
python -m SmartCFDTradingAgent.pipeline --watch BTC-USD ETH-USD --size 2 ^
  --interval 1h --intervals 15m,1h,1d --vote --adx 10 --grace 10 ^
  --risk 0.01 --equity 1000 --cooldown-min 30

python -m SmartCFDTradingAgent.pipeline --watch SPY QQQ DIA IWM --size 4 ^
  --interval 1d --use-params --grace 120 --risk 0.01 --equity 1000 ^
  --max-portfolio-risk 0.02 --max-trades 2

# Show last 10 decisions (and send to Telegram)
python -m SmartCFDTradingAgent.pipeline --show-decisions 10 --to-telegram

# Daily summary to Telegram
python -m SmartCFDTradingAgent.pipeline --daily-summary --tz Europe/Dublin

# Optimize and store best params (ADX/SL/TP) for a watch key
python -m SmartCFDTradingAgent.optimizer --watch SPY QQQ DIA IWM --interval 1d --years 2

python -m SmartCFDTradingAgent.revolut_recon --csv "C:\path\to\Revolut_trades.csv" --window-min 180 --to-telegram
# Output → SmartCFDTradingAgent\storage\recon_YYYY-MM-DD.csv

Automation (Windows Scheduled Tasks)
SCFD_Equities_Pipeline (Mon–Fri) 14:25–21:25 Europe/Dublin, every 30 min → scripts\market_loop.cmd

SCFD_Nightly_Optimizer_Summary daily 22:30 → scripts\nightly.cmd

To run when logged off: Task Scheduler → Properties → Run whether user is logged on or not (store creds).

Repo layout (key bits)
bash
Copy
Edit
SmartCFDTradingAgent_Revolut/
  SmartCFDTradingAgent/
    pipeline.py            # main loop (alerts + backtest + cooldown)
    data_loader.py         # yfinance intraday combos ("7d","1h"), ("30d","60m"), ("30d","30m"), ("7d","15m")
    signals/ indicators/   # EMA, MACD, ADX, ATR
    backtester.py
    position.py            # qty_from_atr()
    optimizer.py           # grid search, writes storage/params.json
    revolut_recon.py       # matches Revolut CSV to decisions
    utils/                 # logger, market_time, telegram, no_ssl
    storage/               # decision_log.csv, params.json, last_signals.json, recon_*.csv
    logs/                  # YYYYMMDD.log (rotated daily)
  scripts/
    run_bot.cmd, market_loop.cmd, nightly.cmd
  .env                     # BOT_TOKEN=..., CHAT_ID=...


Persistence & continuity
Decisions: storage/decision_log.csv

Tuned params: storage/params.json (read by --use-params)

Cooldown state: storage/last_signals.json

Logs: logs/YYYYMMDD.log

Reconciliation: storage/recon_YYYY-MM-DD.csv

Status: SmartCFD v0.1.4 at C:\Projects\SmartCFDTradingAgent_Revolut
Features: voting, optimizer (ADX+SL/TP), ATR qty, cooldown, Telegram, nightly+market tasks
Artifacts: decision_log.csv, params.json, last_signals.json, logs\YYYYMMDD.log


To resume in a new chat, paste:

makefile
Copy
Edit
Status: SmartCFD v0.1.4 at C:\Projects\SmartCFDTradingAgent_Revolut
Features: voting, optimizer (ADX+SL/TP), ATR qty, cooldown, Telegram, nightly+market tasks
Artifacts: decision_log.csv, params.json, last_signals.json, logs\YYYYMMDD.log

Known limits / open items
Walk-forward validation (rolling train/test)

Portfolio caps (max simultaneous alerts, per-asset class caps)

Duplicate-signal cooldown per timeframe

Strategy variants (ATR-based SL/TP live; advanced entries/exits)

Changelog
2025-08-09 — v0.1.4

Intraday fetch via tested period/interval combos `("7d","1h")`, `("30d","60m")`, `("30d","30m")`, `("7d","15m")`

Cooldown + per-line logging

Tuned SL/TP applied when --use-params

Recon tool added

(older phase notes kept below for history)

yaml
Copy
Edit

> I saw your older summary had a short checklist and placeholders; this replaces it with the complete v0.1.4 state and commands, while keeping session-summary lines at the top for continuity. :contentReference[oaicite:0]{index=0}

---

# B) Operator brief `WHERE_WE_ARE.md`

Create: