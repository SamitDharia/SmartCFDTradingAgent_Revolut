# SmartCFDTradingAgent Roadmap (End-to-End)

This roadmap captures the current baseline, outstanding cleanup, development phases (from reliability to ML, backtesting, and deployment), and small PR-sized tasks with acceptance criteria. Designed for incremental delivery and paper-trading first.

## 0) Current Baseline (in main)
- Config + JSON logging
- SQLite persistence
  - runs (record_run)
  - heartbeats (record_heartbeat)
- Runner
  - Periodic Alpaca clock probe with latency; exponential backoff
  - Uses APCA_API_KEY_ID/APCA_API_SECRET_KEY if present
  - Writes heartbeats to SQLite
  - Tiny /healthz HTTP endpoint serving latest heartbeat and freshness
- Docker + CI
  - Container PYTHONPATH fix
  - GHCR workflow pushes sha-<commit> and latest (on main)
- Tests: config/logging, db, heartbeats, Alpaca headers, health compute

Environment (.env at repo root; do not commit secrets)
- TIMEZONE, ALPACA_ENV
- APCA_API_KEY_ID, APCA_API_SECRET_KEY (paper keys for paper env)
- API_TIMEOUT_SECONDS, NETWORK_MAX_BACKOFF_SECONDS
- RUN_HEALTH_SERVER, HEALTH_PORT, HEALTH_MAX_AGE_SECONDS

---

## 1) Cleanup and Hygiene (Immediate)

Why: reduce noise, unify config, prevent confusion, and ensure stable base.

- Env consolidation
  - Ensure all code uses APCA_API_KEY_ID/APCA_API_SECRET_KEY (remove ALPACA_API_* variants)
  - Single template: .env.deploy.example; copy to .env locally
  - Verify .gitignore: ignore *.env, not just .env
  - Acceptance: build_headers_from_env reads APCA_*; no duplicate names in templates or code

- Healthcheck consistency
  - docker/healthcheck.py should first query local /healthz; then fall back to remote Alpaca with headers
  - Acceptance: with no keys, /healthz returns 503; with valid paper keys, 200; logs show correct status

- Backoff and jitter
  - Add small jitter to backoff to avoid thundering herd; cap max sleep by NETWORK_MAX_BACKOFF_SECONDS
  - Acceptance: unit tests for backoff reset on success and capped growth

- Logging polish
  - Include app version/commit in runner.start (via env or injected at build time)
  - Add explicit “auth_detected: true/false” flag on start (no secrets)
  - Acceptance: runner.start extras include version and auth_detected

- Repo hygiene
  - Add pre-commit (ruff, isort/black if desired), mypy baseline, detect-secrets
  - Acceptance: pre-commit runs locally; CI lint + types pass on main

---

## 2) Reliability and Shutdown

- SIGTERM/SIGINT handling
  - Trap signals; record record_run(..., status="stop") and close DB
  - Acceptance: test simulating signal results in “stop” row; no unhandled exceptions

- DB robustness
  - Ensure WAL mode and safe pragmas for SQLite (consider busy_timeout)
  - Acceptance: connection init sets sensible pragmas; test concurrent write scenario (lightweight)

---

## 3) CI Enhancements

- Python tests workflow
  - Run pytest on PRs and main; cache pip; matrix for Python 3.10–3.12 (as feasible)
  - Acceptance: CI green

- Lint + types
  - Ruff (lint), mypy (types) minimal configs to start
  - Acceptance: CI step green; zero errors on current code

- Test artifacts (optional)
  - Upload app.db from test run (or a small generated sample)
  - Acceptance: artifact available in Actions summary

---

## 4) Trading Loop Skeleton (No Orders)

- Market-time gating
  - Poll Alpaca clock/calendar; skip strategy evaluation when market closed
  - Acceptance: mock clock tests; logs show gating behavior

- Strategy interface
  - Define Strategy abstraction: prepare(state) -> None, evaluate(data)->Decision, postprocess(result)
  - No-op strategy emitting hold
  - Acceptance: runner calls strategy on schedule; dry-run only

- State and cadence
  - Configurable evaluation cadence; align to bar close if using minute bars
  - Acceptance: logs reflect cadence and evaluation timing

---

## 5) Alpaca Client Wrapper (Paper Only)

- Typed HTTP client
  - Retry/backoff for transient statuses (429/5xx); timeouts; APCA headers injection
  - Acceptance: responses mocked; retries on configured statuses; no retry on 4xx (except 408/429 if configured)

- Order endpoints (stub)
  - POST order, cancel, list; idempotent client order IDs
  - Acceptance: request shaping and error mapping validated; dry-run mode returns mock responses

---

## 6) Data Pipeline (Offline)

- Historical data fetch
  - Minute bars for chosen symbols with start/end; calendar alignment
  - Fallbacks and local cache (parquet)
  - Acceptance: CLI smartcfd build-dataset --symbol AAPL --start ... --end ... creates dataset and metadata JSON

- Dataset assembly
  - Time-bounded features and labels; time-series splits to avoid leakage (train/val/test)
  - Acceptance: deterministic splits logged; metadata includes time ranges and windows

---

## 7) Feature Engineering

- Feature set v1
  - Returns, rolling means/vol, RSI, MACD, ATR, OBV, gaps, regime flags
  - Calendar features (DOW, proximity to open/close, holidays)
  - Acceptance: pipeline transforms bars->X; schema snapshot/version saved

- Leakage guardrails
  - Strict cutoffs; feature windows limited to lookback
  - Acceptance: tests verifying no future data leakage across split boundaries

---

## 8) Modeling: XGBoost and CatBoost

- Training CLI
  - Classifier (direction/probability) and/or regressor (return)
  - TimeSeriesSplit cross-validation; Optuna or randomized grid with budget
  - Early stopping
  - Metrics: PR-AUC/ROC-AUC/accuracy; regression MSE/MAE and directional accuracy
  - Acceptance: smartcfd train --symbol AAPL --model xgb|cat ... outputs model bundle + report

- Explainability
  - SHAP (sampled) and feature importance
  - Calibration plot for classifier
  - Acceptance: artifacts saved (plots/JSON); logged references to files

- Model persistence
  - Bundle with feature metadata, training config, version, and hash
  - Acceptance: loadable by inference; schema check enforced

---

## 9) Backtesting and Evaluation

- Decision layer
  - Map scores to signals with thresholds; cooldowns; position sizing rules (volatility-scaled option)
  - Acceptance: configurable thresholds; unit tests for rules

- Backtest engine
  - Slippage/fees; portfolio P&L; drawdown; turnover; exposure
  - Walk-forward validation across splits
  - Acceptance: smartcfd backtest --model path --symbol AAPL ... produces JSON summary and plots

- Reports
  - Sharpe, Sortino, max DD, win rate, exposure, stability across threshold ranges
  - Acceptance: summary JSON + PNG/HTML in artifacts/

---

## 10) Strategy Integration in Runner (Dry-Run)

- Inference
  - Load model bundle; maintain rolling feature windows in live loop
  - Log score, top features or feature hash; decision result (no order yet)
  - Acceptance: periodic inference logs; no network order calls; /healthz unchanged

---

## 11) Risk Guardrails and Paper Orders

- Risk config
  - Per-symbol caps; max daily loss; leverage limits; circuit breaker on broker health issues
  - Acceptance: decisions denied when violating limits; logs include reason

- Paper execution
  - Place/cancel orders; reconciliation on reconnect (open orders, positions)
  - Idempotent client order IDs
  - Acceptance: small paper trade e2e; logs + DB reflect lifecycle

---

## 12) Observability

- Daily Digest
  - Generate a daily report (email/Telegram) with:
    - Uptime (health ok ratio, avg latency)
    - Failures (last N errors)
    - Backtest/live-paper P&L summary (if enabled)
    - Positions and risk flags
  - Delivery options: SMTP (email) or Telegram bot (existing utility)
  - Acceptance: CLI smartcfd digest --yesterday outputs Markdown/HTML; sends when configured

- Streamlit Dashboard
  - Read app.db and artifacts; views:
    - Status: last heartbeat, uptime chart, latency distributions
    - Trades/decisions (when enabled): recent decisions, scores, P&L
    - Models: feature importances, SHAP snapshots, calibration
  - Command: streamlit run dashboard/app.py
  - Acceptance: local dashboard loads with sample or live data; responsive filters

- Metrics endpoint (optional)
  - /metrics JSON or Prometheus text for counters (heartbeats_ok, decision_count, error_count)
  - Acceptance: endpoint returns counters; simple scrape-friendly format

- CSV/NDJSON Export
  - Export heartbeats and decisions for offline analysis (CSV/NDJSON)
  - Acceptance: smartcfd export --table heartbeats --out path.csv produces schema with timestamps

---

## 13) Packaging and Deployment

- Docker Compose
  - App service; volume for DB/artifacts; healthcheck uses /healthz; optional dashboard service
  - Acceptance: compose up yields healthy app with keys; dashboard reachable if enabled

- Release workflow
  - Tag-based release builds/pushes image; uploads model/report artifacts
  - Acceptance: GitHub Release contains images + artifacts

---

## 14) Documentation and Runbook

- README overhaul
  - Quickstart (local + Docker), env setup, running tests, keys provisioning, dashboard, digest
- Ops Runbook
  - Health troubleshooting, key rotation, clearing stuck orders, known failure modes, how to halt
- Acceptance: dev can onboard via README; operator can triage with runbook

---

## 15) Live-Readiness Checklist (post-paper)

- Stable backtests and paper performance over defined horizon
- Guardrails enforced; kill-switch verified
- Key rotation rehearsed; alerting routes tested
- Rollback plan documented

---

## Immediate Next PRs (suggested order)

1) core: SIGTERM clean shutdown; record “stop” run row (tests)
2) ci: add pytest workflow; ruff + mypy baselines
3) core: unify env keys (APCA_*), remove duplicates; healthcheck fallback finalized
4) core: market-time gating + strategy interface (no-op strategy)
5) core: typed Alpaca client with retry/backoff; stub order endpoints
6) data: dataset builder CLI + caching; feature pipeline v1; leakage tests
7) ml: training CLI (XGBoost, CatBoost) with time-series CV + early stopping + Optuna/randomized search
8) bt: backtest CLI + metrics + reports
9) core: runner inference (dry-run) wiring
10) risk: guardrails + paper orders e2e
11) obs: daily digest sender (email/Telegram)
12) obs: Streamlit dashboard
13) pkg: docker compose; release workflow
14) docs: README + runbook

---

## Acceptance Check Summary (quick)

- Without keys:
  - runner.health.fail (401); /healthz 503 (not_ok); heartbeats ok=0
- With paper keys:
  - runner.health.ok (200); /healthz 200; heartbeats ok=1; latency logged
- Tests: `pytest -q tests` green on CI and locally

---

## Notes and Choices

- Modeling
  - Start with tabular models: XGBoost, CatBoost; choose classification or regression based on label design
  - TimeSeriesSplit with walk-forward CV; seed for reproducibility
  - Store model + feature metadata and config for exact replays

- Risk
  - Position sizing may be volatility-scaled
  - Circuit breakers for repeated broker failures or health degradation

- Security
  - Secrets never logged; detect-secrets/pre-commit hooks; env-only for keys
  - Rate-limit friendly retries; respect 429

- Performance
  - If needed, move to asyncio or multi-threaded data fetch; keep runner simple first

---

## Branch/PR Conventions

- Branch: `area/topic` (e.g., `core/sigterm-shutdown`, `ci/tests`, `ml/train-xgb`)
- PR title: `scope: action` (e.g., `core: handle SIGTERM and record stop row`)
- Each PR includes:
  - Summary and rationale
  - Testing notes (commands, expectations)
  - Env changes (if any)
  - Rollback plan
