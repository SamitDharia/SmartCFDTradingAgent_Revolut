# Developer Guidance

## Setup
- **Windows CMD**
  ```cmd
  python -m venv .venv
  .venv\Scripts\activate
  pip install -r requirements.txt
  ```
- **WSL/Linux**
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

## Lint
- `ruff .`

## Format
- `black .` (or `black --check .`)

## Tests
- `pytest`

## Smoke/Backtest
- **Windows CMD**
  ```cmd
  python -m SmartCFDTradingAgent --tickers SPY --start 2024-01-01 --end 2024-02-01 --backtest
  ```
- **WSL/Linux**
  ```bash
  python -m SmartCFDTradingAgent --tickers SPY --start 2024-01-01 --end 2024-02-01 --backtest
  ```
