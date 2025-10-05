# Refactor Plan: Alpaca-only Auto Execution, ML Auto-Tuning, Dashboard, and Daily Digest

Status: Proposal (initial PR with this plan)
Owner: @SamitDharia
Scope: Full codebase cleanup and modernization per COPILOT_INSTRUCTIONS.md

## Goals

- Full-auto operation: remove Telegram modules, manual trade execution, and crypto backfill scripts.
- Alpaca-only execution for supported asset classes (equities, crypto; forex/commodities subject to Alpaca support on the target account).
- Machine Learning auto-tuning for strategy parameters and risk modes (conservative ↔ aggressive).
- Premium daily digest (HTML/Markdown) with key metrics.
- Rebuilt Streamlit dashboard with clean “Apple-like” design and real-time insights.
- Simplified, modular architecture with strong logging, configuration, and tests.

## Architecture Overview

Proposed top-level structure:
```
/src
  /adapters
    alpaca_client.py
  /core
    config.py
    logging.py
    data.py
    execution.py
    portfolio.py
    metrics.py
    storage.py
  /strategies
    registry.py
    baselines/
      ema_rsi.py
      macd_adx.py
      bb_breakout.py
  /ml
    tuner.py
    policy.py
  /reporting
    digest.py
  /dashboard
    app.py
  /utils
    timeutils.py, io.py, types.py
/tests
```

Key decisions:
- Persistence: SQLite (trades, orders, metrics, best_params) with a simple schema; CSV exports for portability.
- Config: Pydantic BaseSettings to validate .env, enforce correct keys for paper vs live.
- Logging: Structured (JSON) to file + concise console logs; per-trade, per-strategy, and per-run summaries.
- Extensibility: Strategy registry for plug-and-play indicators and parameter schemas.

## Deletions/Cleanup

- Remove all Telegram-related scripts, configs, and mentions.
- Remove manual trade execution and legacy reporting tied to Telegram/manual flows.
- Remove crypto log backfill utilities (not required per instructions).
- Ensure only Alpaca trade logging remains; centralize in /core/execution.py + /core/storage.py.
- Prune unused/legacy modules and verify imports/dependencies post-removal.

A deletion ledger (docs/deleted-files.md) will be maintained for traceability.

## Alpaca Integration

- Single adapter providing:
  - Account routing (paper vs live) via validated env vars.
  - Market Data v2 for historical/backtest windows and live pricing.
  - Trading API for orders, positions, and status.
- Retry policy, rate limit handling, idempotent order placement.
- Unified trade log: strategy, params, signal, order id, status, fills, PnL attribution.

Open question: confirm asset class scope on your Alpaca account (equities/crypto/forex). Commodities/CFDs generally not supported by Alpaca; propose de-scoping unless you confirm a supported path.

## ML Auto-Tuning

- Tuner targets indicator parameters per strategy (EMA, RSI, MACD, ADX, Bollinger, etc.).
- Approaches:
  - Phase 1: Deterministic grid/random search with early stopping using walk-forward validation.
  - Phase 2: Bayesian optimization (e.g., TPE/GP).
- Objective(s):
  - Primary: Risk-adjusted return (Sharpe/Sortino) with drawdown constraint.
  - Secondary: Hit rate and average win/loss.
- Persistence: best_params table keyed by ticker+strategy+mode (conservative/aggressive).
- Policy: Mode switching based on rolling KPIs and risk budget.

## Daily Digest

- Inputs: Previous session’s trades, positions, KPIs, notable signals.
- Output: HTML (primary) + Markdown fallback, stored under /reports/YYYY-MM-DD.html.
- Contents:
  - Summary metrics: P/L, drawdown, Sharpe, exposure, turnover.
  - Per-strategy performance and notable insights.
  - Rolling KPIs vs benchmarks (persisted in SQLite).
- Delivery: File output first; optional email/slack hooks later.

## Streamlit Dashboard

- Sections:
  - Overview: account, exposure, PnL, drawdown, Sharpe.
  - Strategies: current params, mode, signal heatmap.
  - Trades: timeline and per-trade drill-down.
  - Tuning: latest runs, parameter surfaces, best_params table.
- Design: light theme, whitespace, clean typography; responsive.
- Data source: SQLite + live polling via Alpaca adapter.

## Configuration

- .env with:
  - ALPACA_ENV=paper|live
  - ALPACA_API_KEY_ID / ALPACA_API_SECRET_KEY
  - ALPACA_BASE_URL_PAPER / ALPACA_BASE_URL_LIVE
  - ALPACA_DATA_BASE_URL_PAPER / ALPACA_DATA_BASE_URL_LIVE
  - TICKERS_EQUITIES, TICKERS_CRYPTO, TICKERS_FX (comma-separated)
  - RISK_BUDGETS, MAX_DRAWDOWN, POSITION_LIMITS
  - SAFETY_CONFIRM_LIVE, AUTOTRADE_ENABLED
- Validation: Prevent starting in live mode without explicit confirmation flag.
- Secrets handling: Never logged; redaction in logs.

## Testing Strategy

- Unit tests: strategies, tuner objective, policy switching, metrics, config validation.
- Integration tests: mock Alpaca endpoints for order lifecycle + market data.
- Golden tests: digest HTML snapshots; Streamlit component fixtures.
- Backtest harness: walk-forward runner using Alpaca historical data.
- CI: Lint, type-check, tests; gate merges on coverage thresholds.

## Rollout and Risk Management

- Paper trading first; enforce ALPACA_ENV=paper until acceptance criteria met.
- Feature flags: kill-switch for auto-trading; dry-run mode for order simulation.
- Rollback: tag per milestone; revertible.
- Monitoring: alerts on API failures, abnormal drawdowns, order rejections.

## Acceptance Criteria

- No Telegram/manual/backfill code remains; imports verified.
- Alpaca-only execution with paper/live switching and validation.
- Strategies auto-tune and persist best parameters; KPIs improve on rolling basis.
- Daily digest generated after each session with required metrics.
- Streamlit dashboard loads and displays realtime metrics and strategy state.
- README updated with setup, runbooks, and architecture diagram.
- Deletion ledger present; dependencies trimmed and build green.

## Milestones and Small, Testable Commits

1) Plan PR
- Add this plan and CI skeleton; no runtime changes.

2) Core Scaffolding
- Add config, logging, storage (SQLite), metrics modules.

3) Cleanup Pass
- Remove Telegram/manual/backfill modules; update requirements.

4) Alpaca Adapter + Execution
- Implement adapters/alpaca_client.py and core/execution.py; paper mode only.

5) Data Access + Backtest Harness
- core/data.py for historical + live; walk-forward runner.

6) Strategy Registry + Baselines
- Implement registry and 2–3 baseline strategies.

7) ML Auto-Tuner + Policy
- tuner.py with grid/random first; persistence; policy switching.

8) Daily Digest
- reporting/digest.py producing HTML/MD.

9) Streamlit Dashboard
- dashboard/app.py with pages and charts.

10) Paper → Live Readiness
- Live key validation, safety flags, README, and runbooks.

## Open Questions (will be included in the PR)

1) Asset classes: Which Alpaca classes are enabled (equities, crypto, forex)? Is commodities/CFD out-of-scope?
2) Ticker universe: Provide canonical lists, or should we discover dynamically? Any exclusions?
3) Data plan: Which Alpaca market data subscription level is available? Required bar resolutions/history depth?
4) Risk constraints: Max per-position risk, portfolio drawdown cap, leverage/margin constraints, daily loss limits?
5) Trading cadence: Intraday vs EOD target for v1? Minimum bar resolution?
6) Hosting/runtime: Where will this run (local, VM, container)? Do we need a scheduler for digest/tuning?
7) Legacy persistence: Migrate any historical data into SQLite for KPI continuity?
8) Compliance/logging: Any audit fields or retention requirements beyond this plan?
9) Dashboard distribution: Internal-only for now, or prepare for public demo?
10) CI/CD: Preferred provider and minimum coverage thresholds?

## Timeline (tentative)

- Week 1: Plan PR + scaffolding + cleanup
- Week 2: Alpaca adapter, execution, data access
- Week 3: Strategies + tuner v1 + digest
- Week 4: Dashboard + polish + live readiness.
